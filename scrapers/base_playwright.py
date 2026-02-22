"""Alternative base scraper using standard Playwright instead of Camoufox.

Use this for development/testing on Windows where Camoufox may have issues.
To use: Replace 'from scrapers.base import BaseScraper' with 
'from scrapers.base_playwright import BaseScraper' in clutch.py and sortlist.py
"""

import random
import time
import logging
from typing import Generator
from abc import ABC, abstractmethod

from playwright.sync_api import sync_playwright, Browser, Page

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Base class for site-specific scrapers using standard Playwright.

    Manages the Playwright browser lifecycle and provides shared utilities
    for navigation, delays, and page content extraction.
    """

    def __init__(self, headless: bool | str = True):
        """Initialize scraper.

        Args:
            headless: True for headless mode, False for headed.
        """
        self.headless = True if headless else False
        self._playwright = None
        self._browser: Browser | None = None
        self._page: Page | None = None

    def start_browser(self) -> None:
        """Launch the Playwright Chromium browser and create a page."""
        logger.info("Starting Playwright Chromium browser (headless=%s)", self.headless)
        try:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                ]
            )
            # Create context with realistic viewport and user agent
            context = self._browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            self._page = context.new_page()
            logger.info("Browser started successfully")
        except Exception as e:
            logger.error("Failed to start browser: %s", e)
            raise

    def close_browser(self) -> None:
        """Close the browser and clean up."""
        if self._browser is not None:
            try:
                self._browser.close()
            except Exception as e:
                logger.warning("Error closing browser: %s", e)
            finally:
                self._browser = None
                self._page = None
        
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception as e:
                logger.warning("Error stopping playwright: %s", e)
            finally:
                self._playwright = None
        
        logger.info("Browser closed")

    @property
    def page(self) -> Page:
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
