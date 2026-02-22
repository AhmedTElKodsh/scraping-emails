"""Email extractor — visits company websites to discover contact email addresses."""

import re
import logging
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from config.email_filters import extract_emails_from_text, filter_and_rank_emails

logger = logging.getLogger(__name__)

# Patterns for finding contact/about pages
CONTACT_PAGE_PATTERNS = [
    re.compile(r"/(contact|kontakt|contacto|contato)", re.IGNORECASE),
    re.compile(r"/(about|about-us|a-propos|uber-uns)", re.IGNORECASE),
    re.compile(r"/(team|our-team|equipe)", re.IGNORECASE),
    re.compile(r"/(impressum|imprint|legal)", re.IGNORECASE),
]

# Link text patterns that suggest a contact page
CONTACT_LINK_TEXT = re.compile(
    r"\b(contact|about|team|get.in.touch|reach.us|impressum|imprint)\b",
    re.IGNORECASE,
)


class EmailExtractor:
    """Extracts email addresses from company websites.

    Uses the scraper's existing Playwright page to visit company websites,
    scan the landing page and contact/about pages for email addresses,
    and apply filtering to return the best business contact email.
    """

    def __init__(self, page):
        """Initialize with an existing Playwright page.

        Args:
            page: A Playwright Page object (from the scraper's Camoufox browser).
        """
        self._page = page

    def find_email(self, website_url: str) -> str:
        """Visit a company website and try to find a contact email.

        Strategy:
        1. Navigate to the landing page, extract emails from HTML
        2. If no valid email found, look for contact/about page links
        3. Visit contact page(s) and extract emails
        4. Apply allowlist/blocklist filtering
        5. Return the best email or "Unreachable"

        Args:
            website_url: The company's website URL.

        Returns:
            A valid email address string, or "Unreachable".
        """
        if not website_url or not website_url.startswith("http"):
            return "Unreachable"

        try:
            # Step 1: Check landing page
            logger.info("Checking landing page: %s", website_url)
            self._page.goto(website_url, wait_until="domcontentloaded", timeout=15000)
            self._page.wait_for_timeout(2000)  # Let JS render

            html = self._page.content()
            email = self._extract_best_email(html)
            if email:
                logger.info("Found email on landing page: %s", email)
                return email

            # Step 2: Find and visit contact/about pages
            contact_urls = self._find_contact_page_urls(html, website_url)
            for contact_url in contact_urls[:3]:  # Try up to 3 pages
                try:
                    logger.info("Checking contact page: %s", contact_url)
                    self._page.goto(contact_url, wait_until="domcontentloaded", timeout=10000)
                    self._page.wait_for_timeout(1500)

                    html = self._page.content()
                    email = self._extract_best_email(html)
                    if email:
                        logger.info("Found email on contact page: %s", email)
                        return email
                except Exception as e:
                    logger.debug("Error visiting %s: %s", contact_url, e)
                    continue

            logger.info("No email found for %s", website_url)
            return "Unreachable"

        except Exception as e:
            logger.warning("Error extracting email from %s: %s", website_url, e)
            return "Unreachable"

    def _extract_best_email(self, html: str) -> str | None:
        """Extract emails from HTML and return the best one.

        Combines:
        - mailto: link parsing (highest confidence)
        - Regex extraction from page text
        """
        all_emails = []

        # Parse mailto: links first (highest confidence)
        soup = BeautifulSoup(html, "lxml")
        mailto_links = soup.select('a[href^="mailto:"]')
        for link in mailto_links:
            href = link.get("href", "")
            email = href.replace("mailto:", "").split("?")[0].strip()
            if email:
                all_emails.append(email)

        # Regex extraction from full HTML text
        text_emails = extract_emails_from_text(soup.get_text())
        all_emails.extend(text_emails)

        # Also check HTML source for obfuscated emails
        html_emails = extract_emails_from_text(html)
        all_emails.extend(html_emails)

        # Filter and rank
        return filter_and_rank_emails(all_emails)

    def _find_contact_page_urls(self, html: str, base_url: str) -> list[str]:
        """Find URLs that likely lead to contact or about pages.

        Args:
            html: The landing page HTML.
            base_url: The website's base URL for resolving relative links.

        Returns:
            List of absolute URLs to check, ordered by likelihood.
        """
        soup = BeautifulSoup(html, "lxml")
        candidates = []
        base_domain = urlparse(base_url).netloc

        for a_tag in soup.find_all("a", href=True):
            href = a_tag.get("href", "").strip()
            if not href or href.startswith("#") or href.startswith("javascript:"):
                continue

            full_url = urljoin(base_url, href)

            # Only follow links on the same domain
            if urlparse(full_url).netloc != base_domain:
                continue

            # Check if URL path matches contact page patterns
            path = urlparse(full_url).path
            for pattern in CONTACT_PAGE_PATTERNS:
                if pattern.search(path):
                    candidates.append(full_url)
                    break
            else:
                # Check link text
                link_text = a_tag.get_text(strip=True)
                if link_text and CONTACT_LINK_TEXT.search(link_text):
                    candidates.append(full_url)

        # Deduplicate while preserving order
        seen = set()
        unique = []
        for url in candidates:
            normalized = url.rstrip("/").lower()
            if normalized not in seen:
                seen.add(normalized)
                unique.append(url)

        # Prioritize: contact pages first, then about, then team
        def sort_key(u):
            path = urlparse(u).path.lower()
            if "contact" in path:
                return 0
            if "about" in path:
                return 1
            if "team" in path:
                return 2
            return 3

        unique.sort(key=sort_key)
        return unique
