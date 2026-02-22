"""Live integration tests — require network access and Camoufox browser.

These tests are slower and hit real websites. They verify the full scraping
pipeline works end-to-end against the actual Clutch.co and Sortlist.com sites.

Run with: pytest tests/test_integration_live.py -v -s --timeout=300
Skip with: pytest -m "not live"
"""

import sys
import os
import pytest

# Fix Windows console encoding
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from scrapers.clutch import ClutchScraper
from scrapers.sortlist import SortlistScraper
from extractors.email_extractor import EmailExtractor


# Mark all tests in this module as live (slow, network-dependent)
pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def clutch_scraper():
    """Launch a single Camoufox browser for all Clutch tests."""
    scraper = ClutchScraper(headless=True)
    scraper.start_browser()
    yield scraper
    scraper.close_browser()


@pytest.fixture(scope="module")
def sortlist_scraper():
    """Launch a single Camoufox browser for all Sortlist tests."""
    scraper = SortlistScraper(headless=True)
    scraper.start_browser()
    yield scraper
    scraper.close_browser()


# ── Clutch.co live tests ────────────────────────────────────────────────

class TestClutchLive:
    def test_scrape_developers_finds_companies(self, clutch_scraper):
        """First page of /developers should yield 10+ companies."""
        companies = []
        for company in clutch_scraper.scrape_category("https://clutch.co/developers"):
            companies.append(company)
            if len(companies) >= 15:
                break

        assert len(companies) >= 10, f"Expected 10+ companies, got {len(companies)}"

    def test_company_has_name(self, clutch_scraper):
        companies = []
        for company in clutch_scraper.scrape_category("https://clutch.co/developers"):
            companies.append(company)
            if len(companies) >= 5:
                break

        for c in companies:
            assert c.get("name"), f"Company missing name: {c}"

    def test_company_has_profile_url(self, clutch_scraper):
        companies = []
        for company in clutch_scraper.scrape_category("https://clutch.co/developers"):
            companies.append(company)
            if len(companies) >= 5:
                break

        for c in companies:
            assert c["profile_url"].startswith("https://clutch.co/"), f"Bad profile URL: {c['profile_url']}"

    def test_company_has_location(self, clutch_scraper):
        companies = []
        for company in clutch_scraper.scrape_category("https://clutch.co/developers"):
            companies.append(company)
            if len(companies) >= 5:
                break

        with_location = sum(1 for c in companies if c.get("location"))
        assert with_location >= 3, f"Expected 3+ companies with location, got {with_location}"

    def test_website_url_not_redirect(self, clutch_scraper):
        companies = []
        for company in clutch_scraper.scrape_category("https://clutch.co/developers"):
            companies.append(company)
            if len(companies) >= 5:
                break

        for c in companies:
            url = c.get("website_url", "")
            if url:
                assert "r.clutch.co/redirect" not in url, f"Redirect URL not resolved: {url}"

    def test_source_is_clutch(self, clutch_scraper):
        for company in clutch_scraper.scrape_category("https://clutch.co/developers"):
            assert company["source"] == "Clutch.co"
            break

    def test_email_extraction_from_clutch_company(self, clutch_scraper):
        """Extract email from first company with a website."""
        extractor = EmailExtractor(clutch_scraper.page)
        for company in clutch_scraper.scrape_category("https://clutch.co/developers"):
            if company.get("website_url"):
                email = extractor.find_email(company["website_url"])
                # Either a valid email or "Unreachable" — both are acceptable
                assert email == "Unreachable" or "@" in email
                break


# ── Sortlist.com live tests ─────────────────────────────────────────────

class TestSortlistLive:
    def test_scrape_advertising_finds_companies(self, sortlist_scraper):
        """First page of /advertising should yield 10+ companies."""
        companies = []
        for company in sortlist_scraper.scrape_category("https://www.sortlist.com/advertising"):
            companies.append(company)
            if len(companies) >= 20:
                break

        assert len(companies) >= 10, f"Expected 10+ companies, got {len(companies)}"

    def test_company_has_name(self, sortlist_scraper):
        companies = []
        for company in sortlist_scraper.scrape_category("https://www.sortlist.com/advertising"):
            companies.append(company)
            if len(companies) >= 5:
                break

        for c in companies:
            assert c.get("name"), f"Company missing name: {c}"

    def test_company_has_profile_url(self, sortlist_scraper):
        companies = []
        for company in sortlist_scraper.scrape_category("https://www.sortlist.com/advertising"):
            companies.append(company)
            if len(companies) >= 5:
                break

        for c in companies:
            assert "sortlist.com/agency/" in c["profile_url"], f"Bad profile URL: {c['profile_url']}"

    def test_company_has_location(self, sortlist_scraper):
        companies = []
        for company in sortlist_scraper.scrape_category("https://www.sortlist.com/advertising"):
            companies.append(company)
            if len(companies) >= 5:
                break

        with_location = sum(1 for c in companies if c.get("location"))
        assert with_location >= 3, f"Expected 3+ with location, got {with_location}"

    def test_company_has_website(self, sortlist_scraper):
        companies = []
        for company in sortlist_scraper.scrape_category("https://www.sortlist.com/advertising"):
            companies.append(company)
            if len(companies) >= 5:
                break

        with_website = sum(1 for c in companies if c.get("website_url"))
        assert with_website >= 3, f"Expected 3+ with website, got {with_website}"

    def test_company_has_rating(self, sortlist_scraper):
        companies = []
        for company in sortlist_scraper.scrape_category("https://www.sortlist.com/advertising"):
            companies.append(company)
            if len(companies) >= 5:
                break

        with_rating = sum(1 for c in companies if c.get("rating"))
        assert with_rating >= 3, f"Expected 3+ with rating, got {with_rating}"

    def test_source_is_sortlist(self, sortlist_scraper):
        for company in sortlist_scraper.scrape_category("https://www.sortlist.com/advertising"):
            assert company["source"] == "Sortlist.com"
            break

    def test_email_extraction_from_sortlist_company(self, sortlist_scraper):
        """Extract email from first company with a website."""
        extractor = EmailExtractor(sortlist_scraper.page)
        for company in sortlist_scraper.scrape_category("https://www.sortlist.com/advertising"):
            if company.get("website_url"):
                email = extractor.find_email(company["website_url"])
                assert email == "Unreachable" or "@" in email
                break
