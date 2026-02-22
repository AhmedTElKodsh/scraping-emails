"""Bulk scraper — scrapes all categories from Clutch.co and Sortlist.com into SQLite.

Usage (run from project root):
    python -m v2.scrape_all                          # Scrape first 10 pages + emails
    python -m v2.scrape_all --batch                  # Batch mode: 10 pages, wait 2h, repeat
    python -m v2.scrape_all --batch --interval 1.5   # Batch mode with 1.5h interval
    python -m v2.scrape_all --site Clutch.co         # One site only
    python -m v2.scrape_all --emails-only            # Only email extraction
    python -m v2.scrape_all --max-pages 10           # Pages per batch (default: 10)
    python -m v2.scrape_all --no-emails              # Skip email phase
"""

import argparse
import logging
import sys
import time

from v2.config.categories import get_all_scrape_tasks, SITES
from v2.db.database import Database
from v2.extractors.email_extractor import EmailExtractor

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

MAX_PAGES_DEFAULT = 10
BATCH_INTERVAL_HOURS = 2.0


def main():
    parser = argparse.ArgumentParser(description="Bulk scrape companies into SQLite")
    parser.add_argument("--site", choices=["Clutch.co", "Sortlist.com"], help="Scrape only one site")
    parser.add_argument("--emails-only", action="store_true", help="Only extract emails")
    parser.add_argument("--max-pages", type=int, default=MAX_PAGES_DEFAULT, help="Pages per batch (default: 10)")
    parser.add_argument("--batch", action="store_true", help="Batch mode: scrape N pages, wait, repeat until done")
    parser.add_argument("--interval", type=float, default=BATCH_INTERVAL_HOURS, help="Hours between batches (default: 2)")
    parser.add_argument("--db", default=None, help="Database file path")
    parser.add_argument("--proxy", default="", help="Proxy URL")
    parser.add_argument("--no-emails", action="store_true", help="Skip email extraction")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    db = Database(args.db) if args.db else Database()
    db.connect()

    try:
        if args.emails_only:
            extract_all_emails(db, args.proxy)
        elif args.batch:
            run_batch_loop(db, args)
        else:
            scrape_one_batch(db, args)
            if not args.no_emails:
                extract_all_emails(db, args.proxy)
    except KeyboardInterrupt:
        logger.info("Interrupted by user. Progress saved.")
    finally:
        db.close()
        logger.info("Done.")


def run_batch_loop(db: Database, args):
    """Run scraping in batches: N pages per category, then wait, then next N pages.

    Repeats until all categories have no more pages (hit empty pages).
    """
    batch_num = 0
    interval_secs = args.interval * 3600

    while True:
        batch_num += 1
        logger.info("")
        logger.info("=" * 70)
        logger.info("BATCH %d | %d pages per category | interval: %.1fh", batch_num, args.max_pages, args.interval)
        logger.info("=" * 70)

        had_work = scrape_one_batch(db, args)

        if not had_work:
            logger.info("All categories fully scraped. No more batches needed.")
            break

        # Extract emails for newly scraped companies
        if not args.no_emails:
            extract_all_emails(db, args.proxy)

        # Check if any categories still need more pages
        remaining = db.get_batch_tasks()
        if not remaining:
            logger.info("All categories fully scraped after batch %d.", batch_num)
            break

        logger.info("")
        logger.info("=" * 70)
        logger.info("BATCH %d COMPLETE | %d categories have more pages", batch_num, len(remaining))
        logger.info("Waiting %.1f hours before next batch...", args.interval)
        logger.info("(Press Ctrl+C to stop — progress is saved)")
        logger.info("=" * 70)

        time.sleep(interval_secs)


def scrape_one_batch(db: Database, args) -> bool:
    """Scrape one batch of pages for all categories. Returns True if any work was done."""
    sites = [args.site] if args.site else list(SITES.keys())

    all_tasks = []
    for site in sites:
        for service, field, url in get_all_scrape_tasks(site):
            all_tasks.append((site, service, field, url))

    db.init_scrape_tasks(all_tasks)

    # Get tasks that need work (pending, failed, or batch_done)
    pending = db.get_resumable_tasks()
    if not pending:
        return False

    total = len(all_tasks)
    completed = total - len(pending)

    logger.info("Tasks: %d total, %d completed, %d to process | batch_size=%d pages",
                total, completed, len(pending), args.max_pages)

    for i, task in enumerate(pending, start=1):
        source = task["source"]
        service = task["service"]
        field = task["field"]
        url = task["url"]
        pages_already = task["pages_scraped"] or 0

        # Calculate start page and set MAX_PAGES limit for this batch
        if source == "Clutch.co":
            start_page = pages_already  # 0-indexed
            max_limit = pages_already + args.max_pages
        else:
            start_page = pages_already + 1  # 1-indexed for Sortlist
            max_limit = pages_already + args.max_pages

        logger.info("")
        logger.info("-" * 60)
        logger.info("[%d/%d] %s > %s > %s (pages %d-%d)",
                    i, len(pending), source, service, field,
                    pages_already + 1, pages_already + args.max_pages)
        logger.info("URL: %s", url)
        logger.info("-" * 60)

        db.mark_task_in_progress(source, service, field)

        # Temporarily set MAX_PAGES so the scraper stops after this batch
        orig_clutch_max = _clutch_mod.MAX_PAGES
        orig_sortlist_max = _sortlist_mod.MAX_PAGES
        _clutch_mod.MAX_PAGES = max_limit
        _sortlist_mod.MAX_PAGES = max_limit

        scraper = _create_scraper(source, args.proxy)
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

            new_pages_total = pages_already + args.max_pages

            if company_count == 0:
                # No companies found — this category is fully scraped
                db.mark_task_completed(source, service, field, 0)
                logger.info("Completed (no more pages): %s > %s", service, field)
            else:
                # Got companies — mark as batch_done (more pages may exist)
                db.mark_task_batch_done(source, service, field, new_pages_total, company_count)
                logger.info("Batch done: %d companies from %s > %s (total pages: %d)",
                           company_count, service, field, new_pages_total)

        except Exception as e:
            logger.error("FAILED [%s] %s > %s: %s", source, service, field, e, exc_info=True)
            db.mark_task_failed(source, service, field, str(e))
        finally:
            scraper.close_browser()
            _clutch_mod.MAX_PAGES = orig_clutch_max
            _sortlist_mod.MAX_PAGES = orig_sortlist_max

        time.sleep(5)

    stats = db.get_stats()
    logger.info("")
    logger.info("Batch stats | Total: %d | Clutch: %d | Sortlist: %d",
                stats["total"], stats["clutch_count"], stats["sortlist_count"])

    return True


def extract_all_emails(db: Database, proxy: str = ""):
    """Extract emails for companies that don't have one yet."""
    companies = db.get_pending_email_companies()
    if not companies:
        logger.info("No companies need email extraction.")
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
            name = company["name"]

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
                logger.info("--- Progress: %d/%d | %d emails | %d forms ---", i, len(companies), found, forms)

    finally:
        scraper.close_browser()

    logger.info("")
    logger.info("=" * 70)
    logger.info("EMAIL EXTRACTION COMPLETE | Processed: %d | Emails: %d | Forms: %d",
                len(companies), found, forms)
    logger.info("=" * 70)


def _create_scraper(site: str, proxy_server: str = ""):
    if site == "Clutch.co":
        return ClutchScraper(headless=True, proxy_server=proxy_server)
    else:
        return SortlistScraper(headless=True, proxy_server=proxy_server)


if __name__ == "__main__":
    main()
