"""Tests for scrapers.base module."""

import pytest
from scrapers.base import BaseScraper
from scrapers.clutch import ClutchScraper
from scrapers.sortlist import SortlistScraper


class ConcreteScraper(BaseScraper):
    """Concrete implementation for testing abstract base class."""
    def scrape_category(self, url):
        yield {"name": "test"}

    def get_total_companies(self):
        return 42


class TestBaseScraperInit:
    def test_default_headless(self):
        s = ConcreteScraper()
        assert s.headless is True

    def test_custom_headless(self):
        s = ConcreteScraper(headless="virtual")
        assert s.headless == "virtual"

    def test_headless_false(self):
        s = ConcreteScraper(headless=False)
        assert s.headless is False

    def test_browser_not_started(self):
        s = ConcreteScraper()
        assert s._browser is None
        assert s._page is None
        assert s._context_manager is None


class TestPageProperty:
    def test_raises_before_start(self):
        s = ConcreteScraper()
        with pytest.raises(RuntimeError, match="Browser not started"):
            _ = s.page

    def test_returns_page_when_set(self):
        s = ConcreteScraper()
        s._page = "mock_page"
        assert s.page == "mock_page"


class TestCloseBrowser:
    def test_close_without_start_is_safe(self):
        s = ConcreteScraper()
        s.close_browser()  # Should not raise
        assert s._browser is None

    def test_close_resets_all_fields(self):
        s = ConcreteScraper()
        s._browser = "mock"
        s._page = "mock"

        class FakeContext:
            def __exit__(self, *args):
                pass

        s._context_manager = FakeContext()
        s.close_browser()
        assert s._browser is None
        assert s._page is None
        assert s._context_manager is None


class TestConcreteSubclasses:
    """Verify both concrete scrapers can be instantiated."""

    def test_clutch_scraper_instantiation(self):
        s = ClutchScraper(headless=True)
        assert s._browser is None
        assert isinstance(s, BaseScraper)

    def test_sortlist_scraper_instantiation(self):
        s = SortlistScraper(headless=True)
        assert s._browser is None
        assert s._intercepted_agencies == []
        assert isinstance(s, BaseScraper)
