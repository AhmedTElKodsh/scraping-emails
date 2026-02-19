"""Base scraper with shared Camoufox browser management and utility methods."""

import random
import time
import logging
from typing import Generator
from abc import ABC, abstractmethod

from camoufox.sync_api import Camoufox

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Base class for site-specific scrapers.

    Manages the Camoufox browser lifecycle and provides shared utilities
    for navigation, delays, and page content extraction.
    """

    def __init__(self, headless: bool | str = True):
        """Initialize scraper.

        Args:
            headless: True for standard headless, "virtual" for Xvfb (stealthier in Docker).
        """
        self.headless = headless
        self._browser = None
        self._page = None
        self._camoufox_context = None

    def start_browser(self) -> None:
        """Launch the Camoufox browser and create a page."""
        logger.info("Starting Camoufox browser (headless=%s)", self.headless)
        self._camoufox_context = Camoufox(headless=self.headless)
        self._browser = self._camoufox_context.__enter__()
        self._page = self._browser.new_page()
        logger.info("Browser started successfully")

    def close_browser(self) -> None:
        """Close the browser and clean up."""
        if self._camoufox_context is not None:
            try:
                self._camoufox_context.__exit__(None, None, None)
            except Exception as e:
                logger.warning("Error closing browser: %s", e)
            finally:
                self._browser = None
                self._page = None
                self._camoufox_context = None
            logger.info("Browser closed")

    @property
    def page(self):
        """Get the current page, raising if browser not started."""
        if self._page is None:
            raise RuntimeError("Browser not started. Call start_browser() first.")
        return self._page

    def navigate(self, url: str, wait_until: str = "domcontentloaded") -> None:
        """Navigate to a URL with a random delay beforehand.

        Args:
            url: The URL to navigate to.
            wait_until: Playwright wait condition ("domcontentloaded", "load", "networkidle").
        """
        self.random_delay(1.5, 3.0)
        logger.info("Navigating to: %s", url)
        self.page.goto(url, wait_until=wait_until, timeout=30000)

    def get_page_content(self) -> str:
        """Return the current page's rendered HTML."""
        return self.page.content()

    def random_delay(self, min_s: float = 2.0, max_s: float = 5.0) -> None:
        """Wait a random duration to mimic human behavior."""
        delay = random.uniform(min_s, max_s)
        time.sleep(delay)

    def scroll_page(self) -> None:
        """Scroll down the page to trigger lazy-loaded content."""
        self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1.5)

    @abstractmethod
    def scrape_category(self, url: str) -> Generator[dict, None, None]:
        """Scrape all companies from a category page.

        Yields company dicts one at a time for streaming to the UI.

        Args:
            url: The full category URL to scrape.

        Yields:
            dict with company data fields.
        """
        ...

    @abstractmethod
    def get_total_companies(self) -> int | None:
        """Try to extract the total number of companies from the current page.

        Returns:
            Total count if available, None otherwise.
        """
        ...
