"""Quick smoke test for core components."""

import sys

def test_imports():
    """Test all imports resolve correctly."""
    print("Testing imports...")
    from config.categories import get_category_url, get_categories, get_site_names
    from config.email_filters import is_valid_email, is_preferred_email, extract_emails_from_text, filter_and_rank_emails
    from scrapers.base import BaseScraper
    from scrapers.clutch import ClutchScraper
    from scrapers.sortlist import SortlistScraper
    from extractors.email_extractor import EmailExtractor
    from utils.export import to_csv, to_excel
    print("  All imports OK")

def test_categories():
    """Test category configuration."""
    print("Testing categories...")
    from config.categories import get_site_names, get_categories, get_category_url

    sites = get_site_names()
    assert sites == ["Clutch.co", "Sortlist.com"], f"Unexpected sites: {sites}"

    clutch_cats = get_categories("Clutch.co")
    assert "Development" in clutch_cats
    assert "IT Services" in clutch_cats
    assert len(clutch_cats) == 5, f"Expected 5 Clutch categories, got {len(clutch_cats)}"

    sortlist_cats = get_categories("Sortlist.com")
    assert "Advertising & Marketing" in sortlist_cats
    assert len(sortlist_cats) == 4, f"Expected 4 Sortlist categories, got {len(sortlist_cats)}"

    url = get_category_url("Clutch.co", "Development")
    assert url == "https://clutch.co/developers", f"Unexpected URL: {url}"

    url = get_category_url("Sortlist.com", "Advertising & Marketing")
    assert url == "https://www.sortlist.com/advertising", f"Unexpected URL: {url}"

    print("  Categories OK")

def test_email_filters():
    """Test email filtering logic."""
    print("Testing email filters...")
    from config.email_filters import is_valid_email, is_preferred_email, filter_and_rank_emails

    # Valid business emails
    assert is_valid_email("info@company.com") == True
    assert is_valid_email("hello@agency.io") == True
    assert is_valid_email("contact@firm.co.uk") == True
    assert is_valid_email("john@company.com") == True

    # Blocked emails
    assert is_valid_email("noreply@company.com") == False
    assert is_valid_email("no-reply@company.com") == False
    assert is_valid_email("unsubscribe@company.com") == False
    assert is_valid_email("test@sentry.io") == False
    assert is_valid_email("user@wixpress.com") == False
    assert is_valid_email("a@example.com") == False
    assert is_valid_email("image.png@fake.com") == False

    # Preferred emails
    assert is_preferred_email("info@company.com") == True
    assert is_preferred_email("contact@company.com") == True
    assert is_preferred_email("john@company.com") == False

    # Ranking
    emails = ["john@company.com", "noreply@company.com", "info@company.com"]
    best = filter_and_rank_emails(emails)
    assert best == "info@company.com", f"Expected info@company.com, got {best}"

    emails = ["noreply@company.com", "unsubscribe@company.com"]
    best = filter_and_rank_emails(emails)
    assert best is None, f"Expected None, got {best}"

    emails = ["john@company.com", "jane@company.com"]
    best = filter_and_rank_emails(emails)
    assert best == "john@company.com", f"Expected john@company.com, got {best}"

    print("  Email filters OK")

def test_export():
    """Test CSV/Excel export."""
    print("Testing export...")
    import pandas as pd
    from utils.export import to_csv, to_excel

    df = pd.DataFrame([
        {"name": "Test Co", "email": "info@test.com", "rating": "4.5"},
        {"name": "Demo Inc", "email": "Unreachable", "rating": "4.0"},
    ])

    csv_bytes = to_csv(df)
    assert isinstance(csv_bytes, bytes)
    assert b"Test Co" in csv_bytes
    assert b"info@test.com" in csv_bytes
    print(f"  CSV export OK ({len(csv_bytes)} bytes)")

    excel_bytes = to_excel(df)
    assert isinstance(excel_bytes, bytes)
    assert len(excel_bytes) > 0
    print(f"  Excel export OK ({len(excel_bytes)} bytes)")

def test_scraper_init():
    """Test scraper instantiation (no browser launch)."""
    print("Testing scraper instantiation...")
    from scrapers.clutch import ClutchScraper
    from scrapers.sortlist import SortlistScraper

    cs = ClutchScraper(headless=True)
    assert cs._browser is None
    assert cs._page is None

    ss = SortlistScraper(headless=True)
    assert ss._browser is None
    assert ss._intercepted_agencies == []
    assert ss._response_handler is None

    print("  Scraper instantiation OK")

def test_camoufox_launch():
    """Test Camoufox browser can launch and close."""
    print("Testing Camoufox browser launch...")
    from scrapers.clutch import ClutchScraper

    scraper = ClutchScraper(headless=True)
    try:
        scraper.start_browser()
        assert scraper._browser is not None
        assert scraper._page is not None
        print("  Browser launched OK")

        # Navigate to a simple page
        scraper.page.goto("https://httpbin.org/html", wait_until="domcontentloaded", timeout=15000)
        html = scraper.get_page_content()
        assert "Herman Melville" in html, "Expected content from httpbin.org/html"
        print("  Navigation OK")

    finally:
        scraper.close_browser()
        assert scraper._browser is None
        print("  Browser closed OK")


if __name__ == "__main__":
    passed = 0
    failed = 0
    errors = []

    tests = [
        test_imports,
        test_categories,
        test_email_filters,
        test_export,
        test_scraper_init,
        test_camoufox_launch,
    ]

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            errors.append((test.__name__, str(e)))
            print(f"  FAILED: {e}")

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed")
    if errors:
        print("\nFailures:")
        for name, err in errors:
            print(f"  - {name}: {err}")
        sys.exit(1)
    else:
        print("All tests passed!")
