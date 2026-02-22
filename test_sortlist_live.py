"""Live integration test — scrape first page of Sortlist.com Advertising category."""

import sys
import os
import logging

# Fix Windows console encoding for international characters
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from scrapers.sortlist import SortlistScraper
from extractors.email_extractor import EmailExtractor

# Show debug logs for API interception
logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s: %(message)s")


def test_sortlist_first_page():
    """Scrape the first page of Sortlist.com /advertising and extract emails for the first 3 companies."""
    print("=" * 60)
    print("LIVE TEST: Sortlist.com /advertising (first page only)")
    print("=" * 60)

    scraper = SortlistScraper(headless=True)
    companies = []

    try:
        scraper.start_browser()
        email_extractor = EmailExtractor(scraper.page)

        url = "https://www.sortlist.com/advertising"
        print(f"\nNavigating to: {url}")

        count = 0
        for company in scraper.scrape_category(url):
            count += 1
            companies.append(company)
            print(f"\n--- Company #{count} ---")
            print(f"  Name:     {company.get('name', 'N/A')}")
            print(f"  Rating:   {company.get('rating', 'N/A')}")
            print(f"  Reviews:  {company.get('reviews_count', 'N/A')}")
            print(f"  Location: {company.get('location', 'N/A')}")
            print(f"  Website:  {company.get('website_url', 'N/A')}")
            print(f"  Profile:  {company.get('profile_url', 'N/A')}")
            services = company.get('services', 'N/A')
            print(f"  Services: {services[:80] if services else 'N/A'}")
            print(f"  Team:     {company.get('team_size', 'N/A')}")

            # Test email extraction on first 3 companies with websites
            if count <= 3 and company.get("website_url"):
                print(f"  Extracting email from {company['website_url']}...")
                email = email_extractor.find_email(company["website_url"])
                company["email"] = email
                print(f"  Email:    {email}")

            # Stop after first page
            if count >= 20:
                print(f"\n(Stopping after {count} companies - first page test)")
                break

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        scraper.close_browser()

    # Report
    print(f"\n{'=' * 60}")
    print(f"RESULTS:")
    print(f"  Companies found: {len(companies)}")
    names_found = sum(1 for c in companies if c.get("name"))
    print(f"  With names:      {names_found}")
    locations_found = sum(1 for c in companies if c.get("location"))
    print(f"  With locations:  {locations_found}")
    websites_found = sum(1 for c in companies if c.get("website_url"))
    print(f"  With websites:   {websites_found}")
    emails_found = sum(1 for c in companies if c.get("email") and c["email"] != "Unreachable")
    emails_tested = sum(1 for c in companies if c.get("email"))
    print(f"  Emails tested:   {emails_tested}")
    print(f"  Emails found:    {emails_found}")

    if len(companies) == 0:
        print("\nFAILED: No companies extracted!")
        return False

    if names_found == 0:
        print("\nFAILED: No company names extracted!")
        return False

    print(f"\nPASS: Extracted {len(companies)} companies from Sortlist.com")
    return True


if __name__ == "__main__":
    success = test_sortlist_first_page()
    sys.exit(0 if success else 1)
