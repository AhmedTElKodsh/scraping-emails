"""Live integration test — simulate "Both" mode: Clutch + Sortlist sequentially."""

import sys
import os

# Fix Windows console encoding
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import logging
import pandas as pd

from scrapers.clutch import ClutchScraper
from scrapers.sortlist import SortlistScraper
from extractors.email_extractor import EmailExtractor
from config.categories import get_category_url

logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s: %(message)s")


def test_both_mode():
    """Simulate the app's 'Both' mode — Clutch then Sortlist, 5 companies each."""
    print("=" * 60)
    print("LIVE TEST: Both mode (Clutch + Sortlist)")
    print("=" * 60)

    all_data = pd.DataFrame()
    tasks = [
        ("Clutch.co", "Development", get_category_url("Clutch.co", "Development")),
        ("Sortlist.com", "Advertising & Marketing", get_category_url("Sortlist.com", "Advertising & Marketing")),
    ]

    for site, category, url in tasks:
        print(f"\n{'—' * 50}")
        print(f"Scraping: {site} / {category}")
        print(f"URL: {url}")
        print(f"{'—' * 50}")

        if site == "Clutch.co":
            scraper = ClutchScraper(headless=True)
        else:
            scraper = SortlistScraper(headless=True)

        try:
            scraper.start_browser()
            email_extractor = EmailExtractor(scraper.page)

            count = 0
            for company in scraper.scrape_category(url):
                count += 1
                print(f"  [{site}] #{count}: {company.get('name', 'N/A')} | {company.get('location', 'N/A')}")

                # Extract email for first 2 per site
                if count <= 2 and company.get("website_url"):
                    email = email_extractor.find_email(company["website_url"])
                    company["email"] = email
                    status = email if email != "Unreachable" else "Unreachable"
                    print(f"           Email: {status}")

                new_row = pd.DataFrame([company])
                all_data = pd.concat([all_data, new_row], ignore_index=True)

                if count >= 5:
                    break

        except Exception as e:
            print(f"  ERROR on {site}: {e}")
            import traceback
            traceback.print_exc()

        finally:
            scraper.close_browser()
            print(f"  Browser closed for {site}")

    # Report
    print(f"\n{'=' * 60}")
    print("COMBINED RESULTS:")
    print(f"  Total companies: {len(all_data)}")

    sources = all_data.get("source", pd.Series())
    clutch_count = (sources == "Clutch.co").sum() if not sources.empty else 0
    sortlist_count = (sources == "Sortlist.com").sum() if not sources.empty else 0
    print(f"  From Clutch.co:    {clutch_count}")
    print(f"  From Sortlist.com: {sortlist_count}")

    names = sum(1 for _, r in all_data.iterrows() if r.get("name"))
    emails_found = sum(1 for _, r in all_data.iterrows() if r.get("email") and r["email"] != "Unreachable")
    emails_tested = sum(1 for _, r in all_data.iterrows() if r.get("email"))
    print(f"  With names:        {names}")
    print(f"  Emails tested:     {emails_tested}")
    print(f"  Emails found:      {emails_found}")

    # Validate
    ok = True
    if clutch_count == 0:
        print("\nFAILED: No Clutch companies!")
        ok = False
    if sortlist_count == 0:
        print("\nFAILED: No Sortlist companies!")
        ok = False
    if names == 0:
        print("\nFAILED: No company names!")
        ok = False

    if ok:
        print(f"\nPASS: Both mode works — {clutch_count} Clutch + {sortlist_count} Sortlist companies")
    return ok


if __name__ == "__main__":
    success = test_both_mode()
    sys.exit(0 if success else 1)
