"""Base scraper with browser management and utility methods.

Supports two browser backends controlled by the BROWSER_ENGINE env var:
  - "playwright" (default): Standard Playwright Chromium — reliable on all platforms.
  - "camoufox": Camoufox (Firefox antidetect) — stealthier, best on Linux/Docker.
"""

import os
import random
import time
import logging
from typing import Generator
from abc import ABC, abstractmethod

from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

BROWSER_ENGINE = os.environ.get("BROWSER_ENGINE", "playwright").lower()


def _try_import_camoufox():
    """Import Camoufox only when needed (avoids hangs on unsupported platforms)."""
    try:
        from camoufox.sync_api import Camoufox
        return Camoufox
    except ImportError:
        logger.warning("camoufox not installed, falling back to playwright")
        return None


class BaseScraper(ABC):
    """Base class for site-specific scrapers.

    Manages the browser lifecycle and provides shared utilities
    for navigation, delays, and page content extraction.
    """

    def __init__(self, headless: bool | str = True, proxy_server: str = ""):
        """Initialize scraper.

        Args:
            headless: True for standard headless, "virtual" for Xvfb (stealthier in Docker).
            proxy_server: Optional proxy URL, e.g. "http://user:pass@host:port".
        """
        self.headless = headless
        self.proxy_server = proxy_server
        self._browser = None
        self._page = None
        self._context_manager = None  # Camoufox context or None
        self._playwright = None       # Playwright instance or None

    def start_browser(self) -> None:
        """Launch the browser (Playwright or Camoufox based on BROWSER_ENGINE)."""
        if BROWSER_ENGINE == "camoufox":
            self._start_camoufox()
        else:
            self._start_playwright()

    def _start_playwright(self) -> None:
        """Launch Playwright Chromium browser."""
        logger.info("Starting Playwright Chromium (headless=%s, proxy=%s)", self.headless, bool(self.proxy_server))
        headless = True if self.headless is True or self.headless == "virtual" else bool(self.headless)
        proxy = {"server": self.proxy_server} if self.proxy_server else None
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=headless,
            proxy=proxy,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ],
        )
        context = self._browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            # ScraperAPI (and other MITM proxies) use their own SSL cert;
            # without this flag every HTTPS request through the proxy fails.
            ignore_https_errors=bool(self.proxy_server),
        )
        self._page = context.new_page()
        logger.info("Playwright browser started successfully")

    def _start_camoufox(self) -> None:
        """Launch Camoufox Firefox browser."""
        Camoufox = _try_import_camoufox()
        if Camoufox is None:
            logger.warning("Camoufox unavailable, using Playwright instead")
            self._start_playwright()
            return
        logger.info("Starting Camoufox browser (headless=%s, proxy=%s)", self.headless, bool(self.proxy_server))
        proxy = {"server": self.proxy_server} if self.proxy_server else None
        self._context_manager = Camoufox(headless=self.headless, proxy=proxy)
        self._browser = self._context_manager.__enter__()
        self._page = self._browser.new_page()
        logger.info("Camoufox browser started successfully")

    def close_browser(self) -> None:
        """Close the browser and clean up."""
        if self._context_manager is not None:
            try:
                self._context_manager.__exit__(None, None, None)
            except Exception as e:
                logger.warning("Error closing Camoufox: %s", e)
            finally:
                self._context_manager = None
        if self._browser is not None and self._playwright is not None:
            try:
                self._browser.close()
            except Exception as e:
                logger.warning("Error closing Playwright browser: %s", e)
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception as e:
                logger.warning("Error stopping Playwright: %s", e)
            finally:
                self._playwright = None
        self._browser = None
        self._page = None
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
    def scrape_category(self, url: str, start_page: int = 0) -> Generator[dict, None, None]:
        """Scrape all companies from a category page.

        Yields company dicts one at a time for streaming to the UI.

        Args:
            url: The full category URL to scrape.
            start_page: Page to start from (default 0). Enables batch resuming.

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
