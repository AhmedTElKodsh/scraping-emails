"""Bulk scraper — scrapes Clutch.co and Sortlist.com into SQLite, extracts emails, exports files.

Default behaviour (just run this):
    python -m v2.scrape_all

What it does automatically, forever until all pages are done:
    1. Scrape next 10 pages of every category
    2. Extract emails for every newly scraped company
    3. Export CSV/Excel files split by service type
    4. Send files via email
    5. Wait 2 hours
    6. Repeat from step 1 (picking up where it left off)
    7. Stop when all categories are fully scraped

Optional overrides (all have defaults in .env):
    python -m v2.scrape_all --site Clutch.co        # one site only
    python -m v2.scrape_all --max-pages 5           # 5 pages per batch instead of 10
    python -m v2.scrape_all --interval 1            # wait 1 hour between batches
    python -m v2.scrape_all --no-export             # skip export/email step
"""

import argparse
import logging
import sys
import time
from pathlib import Path

from v2.config.categories import get_all_scrape_tasks, SITES
from v2.config.settings import (
    EMAIL_TO, EMAIL_FROM, EMAIL_PASSWORD,
    PROXY_URL, MAX_PAGES, BATCH_INTERVAL_HOURS,
    DB_PATH, OUTPUT_DIR,
)
from v2.db.database import Database
from v2.extractors.email_extractor import EmailExtractor
from v2.export_data import export_all

from scrapers.clutch import ClutchScraper
from scrapers.sortlist import SortlistScraper

import scrapers.clutch as _clutch_mod
import scrapers.sortlist as _sortlist_mod

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Scrape → extract emails → export → wait → repeat (settings from .env)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--site", choices=["Clutch.co", "Sortlist.com"],
                        help="Scrape only one site (default: both)")
    parser.add_argument("--max-pages", type=int, default=None,
                        help=f"Pages to scrape per category per batch (default from .env: {MAX_PAGES})")
    parser.add_argument("--interval", type=float, default=None,
                        help=f"Hours to wait between batches (default from .env: {BATCH_INTERVAL_HOURS})")
    parser.add_argument("--db", default=None,
                        help=f"Database file path (default from .env: {DB_PATH})")
    parser.add_argument("--proxy", default=None,
                        help="Proxy URL (default from .env: PROXY_URL)")
    parser.add_argument("--no-export", action="store_true",
                        help="Skip export and email step after each batch")
    args = parser.parse_args()

    # Apply .env defaults for anything not passed on CLI
    max_pages    = args.max_pages or MAX_PAGES
    interval     = args.interval  or BATCH_INTERVAL_HOURS
    proxy        = args.proxy     or PROXY_URL
    db_path      = args.db        or DB_PATH
    output_dir   = Path(OUTPUT_DIR)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    db = Database(db_path)
    db.connect()

    try:
        _run_loop(db, args.site, max_pages, interval, proxy, output_dir, args.no_export)
    except KeyboardInterrupt:
        logger.info("")
        logger.info("Interrupted by user. Progress is saved — re-run to continue.")
        if not args.no_export:
            _export_and_send(db, output_dir)
    finally:
        db.close()
        logger.info("Done.")


def _run_loop(
    db: Database,
    site_filter: str | None,
    max_pages: int,
    interval_hours: float,
    proxy: str,
    output_dir: Path,
    no_export: bool,
):
    """Main loop: scrape batch → extract emails → export → wait → repeat."""
    interval_secs = interval_hours * 3600
    batch_num = 0

    while True:
        batch_num += 1

        # ── 1. Scrape next N pages ────────────────────────────────
        logger.info("")
        logger.info("=" * 70)
        logger.info("BATCH %d  |  %d pages/category  |  interval: %.1fh",
                    batch_num, max_pages, interval_hours)
        logger.info("=" * 70)

        had_work = _scrape_batch(db, site_filter, max_pages, proxy)

        if not had_work:
            logger.info("All categories fully scraped. Nothing left to do.")
            break

        # ── 2. Extract emails for newly scraped companies ─────────
        _extract_emails(db, proxy)

        # ── 3. Export CSV/Excel + send email ──────────────────────
        if not no_export:
            _export_and_send(db, output_dir)

        # ── 4. Check if more batches are needed ───────────────────
        remaining = db.get_batch_tasks()
        if not remaining:
            logger.info("All categories fully scraped after batch %d.", batch_num)
            break

        logger.info("")
        logger.info("=" * 70)
        logger.info("BATCH %d COMPLETE  |  %d categories still have more pages",
                    batch_num, len(remaining))
        logger.info("Waiting %.1f hours before next batch...", interval_hours)
        logger.info("(Press Ctrl+C to stop — progress is saved and will resume here)")
        logger.info("=" * 70)

        # ── 5. Wait ───────────────────────────────────────────────
        time.sleep(interval_secs)


def _scrape_batch(db: Database, site_filter: str | None, max_pages: int, proxy: str) -> bool:
    """Scrape one batch of pages for all categories. Returns True if any work was done."""
    sites = [site_filter] if site_filter else list(SITES.keys())

    all_tasks = []
    for site in sites:
        for service, field, url in get_all_scrape_tasks(site):
            all_tasks.append((site, service, field, url))

    db.init_scrape_tasks(all_tasks)

    pending = db.get_resumable_tasks()
    if not pending:
        return False

    total = len(all_tasks)
    done  = total - len(pending)
    logger.info("Tasks: %d total | %d done | %d to process this batch", total, done, len(pending))

    for i, task in enumerate(pending, start=1):
        source        = task["source"]
        service       = task["service"]
        field         = task["field"]
        url           = task["url"]
        pages_already = task["pages_scraped"] or 0

        if source == "Clutch.co":
            start_page = pages_already          # 0-indexed
        else:
            start_page = pages_already + 1      # 1-indexed for Sortlist
        max_limit = pages_already + max_pages

        logger.info("")
        logger.info("-" * 60)
        logger.info("[%d/%d] %s > %s > %s  (pages %d-%d)",
                    i, len(pending), source, service, field,
                    pages_already + 1, pages_already + max_pages)
        logger.info("URL: %s", url)
        logger.info("-" * 60)

        db.mark_task_in_progress(source, service, field)

        orig_clutch_max   = _clutch_mod.MAX_PAGES
        orig_sortlist_max = _sortlist_mod.MAX_PAGES
        _clutch_mod.MAX_PAGES   = max_limit
        _sortlist_mod.MAX_PAGES = max_limit

        scraper = _create_scraper(source, proxy)
        try:
            scraper.start_browser()
            company_count = 0

            for company_data in scraper.scrape_category(url, start_page=start_page):
                if not company_data.get("name"):
                    continue
                company_id = db.upsert_company(company_data)
                db.add_category(company_id, service, field, source)
                company_count += 1
                if company_count % 25 == 0:
                    logger.info("  ... %d companies so far", company_count)

            if company_count == 0:
                db.mark_task_completed(source, service, field, 0)
                logger.info("Completed (no more pages): %s > %s", service, field)
            else:
                db.mark_task_batch_done(source, service, field,
                                        pages_already + max_pages, company_count)
                logger.info("Batch done: %d companies | %s > %s (total pages scraped: %d)",
                            company_count, service, field, pages_already + max_pages)

        except Exception as e:
            logger.error("FAILED [%s] %s > %s: %s", source, service, field, e, exc_info=True)
            db.mark_task_failed(source, service, field, str(e))
        finally:
            scraper.close_browser()
            _clutch_mod.MAX_PAGES   = orig_clutch_max
            _sortlist_mod.MAX_PAGES = orig_sortlist_max

        time.sleep(5)

    stats = db.get_stats()
    logger.info("")
    logger.info("Scrape stats | Total: %d | Clutch: %d | Sortlist: %d",
                stats["total"], stats["clutch_count"], stats["sortlist_count"])
    return True


def _extract_emails(db: Database, proxy: str = ""):
    """Extract emails for all companies that haven't been processed yet."""
    companies = db.get_pending_email_companies()
    if not companies:
        logger.info("No new companies need email extraction.")
        return

    logger.info("")
    logger.info("=" * 70)
    logger.info("EMAIL EXTRACTION: %d companies to process", len(companies))
    logger.info("=" * 70)

    scraper = _create_scraper("Clutch.co", proxy)
    found = 0
    forms = 0

    try:
        scraper.start_browser()
        extractor = EmailExtractor(scraper.page)

        for i, company in enumerate(companies, start=1):
            website_url = company["website_url"]
            name        = company["name"]

            if not website_url:
                db.update_email(company["id"], "Unreachable", "")
                continue

            logger.info("[%d/%d] %s | %s", i, len(companies), name, website_url[:60])

            try:
                email, contact_form_url = extractor.find_email(website_url)
                db.update_email(company["id"], email, contact_form_url)

                if email and email != "Unreachable":
                    found += 1
                    logger.info("  -> Email: %s", email)
                elif contact_form_url:
                    forms += 1
                    logger.info("  -> Contact form: %s", contact_form_url)
                else:
                    logger.info("  -> Unreachable")
            except Exception as e:
                logger.warning("  -> Error: %s", e)
                db.update_email(company["id"], "Unreachable", "")

            time.sleep(1)

            if i % 50 == 0:
                logger.info("--- Progress: %d/%d | %d emails | %d forms ---",
                            i, len(companies), found, forms)
    finally:
        scraper.close_browser()

    logger.info("")
    logger.info("=" * 70)
    logger.info("EMAIL EXTRACTION DONE | Processed: %d | Emails: %d | Forms: %d",
                len(companies), found, forms)
    logger.info("=" * 70)


def _export_and_send(db: Database, output_dir: Path):
    logger.info("")
    logger.info("=" * 70)
    logger.info("EXPORTING DATA")
    logger.info("=" * 70)
    export_all(db, output_dir,
               email_to=EMAIL_TO, email_from=EMAIL_FROM, email_password=EMAIL_PASSWORD)


def _create_scraper(site: str, proxy_server: str = ""):
    if site == "Clutch.co":
        return ClutchScraper(headless=True, proxy_server=proxy_server)
    return SortlistScraper(headless=True, proxy_server=proxy_server)


if __name__ == "__main__":
    main()
