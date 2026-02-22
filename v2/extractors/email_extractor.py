"""Enhanced email extractor for v2 — returns (email, contact_form_url) tuples.

Improvements over v1:
  - Returns contact form URL when no email found
  - Uses email-scraper library for obfuscated email detection (atob, HTML entities)
  - Enhanced contact form detection heuristics
  - More contact page URL patterns
"""

import re
import logging
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

# Import from the original config (shared with v1)
from config.email_filters import extract_emails_from_text, filter_and_rank_emails

logger = logging.getLogger(__name__)

# Try importing email-scraper for obfuscated email detection
try:
    from email_scraper import scrape_emails as _scrape_obfuscated
except ImportError:
    _scrape_obfuscated = None
    logger.debug("email-scraper not installed; obfuscated email detection disabled")

# Patterns for finding contact/about pages
CONTACT_PAGE_PATTERNS = [
    re.compile(r"/(contact|kontakt|contacto|contato|contactez)", re.IGNORECASE),
    re.compile(r"/(about|about-us|a-propos|uber-uns)", re.IGNORECASE),
    re.compile(r"/(team|our-team|equipe)", re.IGNORECASE),
    re.compile(r"/(impressum|imprint|legal)", re.IGNORECASE),
    re.compile(r"/(get-in-touch|reach-us|support)", re.IGNORECASE),
]

CONTACT_LINK_TEXT = re.compile(
    r"\b(contact|about|team|get.in.touch|reach.us|impressum|imprint|support)\b",
    re.IGNORECASE,
)

CONTACT_FORM_FIELD_TYPES = {"text", "email", "tel"}
CONTACT_FORM_KEYWORDS = re.compile(
    r"(message|inquiry|enquiry|contact|comment|feedback|question|subject|your.?name|your.?email)",
    re.IGNORECASE,
)


class EmailExtractor:
    """Extracts email addresses from company websites.

    Returns (email, contact_form_url) tuples.
    """

    def __init__(self, page):
        self._page = page

    def find_email(self, website_url: str) -> tuple[str, str]:
        """Visit a company website and try to find a contact email.

        Returns:
            (email, contact_form_url) tuple.
            email: valid address or "Unreachable"
            contact_form_url: URL of contact form page if found, else ""
        """
        if not website_url or not website_url.startswith("http"):
            return ("Unreachable", "")

        contact_form_url = ""

        try:
            logger.info("Checking landing page: %s", website_url)
            self._page.goto(website_url, wait_until="domcontentloaded", timeout=15000)
            self._page.wait_for_timeout(2000)

            html = self._page.content()
            email = self._extract_best_email(html)
            if email:
                logger.info("Found email on landing page: %s", email)
                return (email, "")

            if self._has_contact_form(html):
                contact_form_url = website_url

            contact_urls = self._find_contact_page_urls(html, website_url)
            for contact_url in contact_urls[:3]:
                try:
                    logger.info("Checking contact page: %s", contact_url)
                    self._page.goto(contact_url, wait_until="domcontentloaded", timeout=10000)
                    self._page.wait_for_timeout(1500)

                    html = self._page.content()
                    email = self._extract_best_email(html)
                    if email:
                        logger.info("Found email on contact page: %s", email)
                        return (email, "")

                    if not contact_form_url and self._has_contact_form(html):
                        contact_form_url = contact_url
                except Exception as e:
                    logger.debug("Error visiting %s: %s", contact_url, e)
                    continue

            logger.info("No email found for %s", website_url)
            return ("Unreachable", contact_form_url)

        except Exception as e:
            logger.warning("Error extracting email from %s: %s", website_url, e)
            return ("Unreachable", contact_form_url)

    def _extract_best_email(self, html: str) -> str | None:
        all_emails = []

        soup = BeautifulSoup(html, "lxml")
        for link in soup.select('a[href^="mailto:"]'):
            href = link.get("href", "")
            email = href.replace("mailto:", "").split("?")[0].strip()
            if email:
                all_emails.append(email)

        if _scrape_obfuscated is not None:
            try:
                obfuscated = _scrape_obfuscated(html)
                if obfuscated:
                    all_emails.extend(obfuscated)
            except Exception:
                pass

        text_emails = extract_emails_from_text(soup.get_text())
        all_emails.extend(text_emails)

        html_emails = extract_emails_from_text(html)
        all_emails.extend(html_emails)

        return filter_and_rank_emails(all_emails)

    def _has_contact_form(self, html: str) -> bool:
        soup = BeautifulSoup(html, "lxml")
        for form in soup.find_all("form"):
            action = (form.get("action", "") or "").lower()
            if "search" in action:
                continue
            cls = form.get("class", []) or []
            if any("search" in c.lower() for c in cls):
                continue

            inputs = form.find_all("input")
            textareas = form.find_all("textarea")
            contact_inputs = 0

            for inp in inputs:
                inp_type = (inp.get("type", "text") or "text").lower()
                inp_name = (inp.get("name", "") or "").lower()
                inp_placeholder = (inp.get("placeholder", "") or "").lower()
                if inp_type in CONTACT_FORM_FIELD_TYPES:
                    contact_inputs += 1
                if CONTACT_FORM_KEYWORDS.search(inp_name) or CONTACT_FORM_KEYWORDS.search(inp_placeholder):
                    return True

            if textareas and contact_inputs >= 1:
                return True
            if contact_inputs >= 3:
                return True

        return False

    def _find_contact_page_urls(self, html: str, base_url: str) -> list[str]:
        soup = BeautifulSoup(html, "lxml")
        candidates = []
        base_domain = urlparse(base_url).netloc

        for a_tag in soup.find_all("a", href=True):
            href = a_tag.get("href", "").strip()
            if not href or href.startswith("#") or href.startswith("javascript:"):
                continue
            full_url = urljoin(base_url, href)
            if urlparse(full_url).netloc != base_domain:
                continue

            path = urlparse(full_url).path
            matched = False
            for pattern in CONTACT_PAGE_PATTERNS:
                if pattern.search(path):
                    candidates.append(full_url)
                    matched = True
                    break
            if not matched:
                link_text = a_tag.get_text(strip=True)
                if link_text and CONTACT_LINK_TEXT.search(link_text):
                    candidates.append(full_url)

        seen = set()
        unique = []
        for url in candidates:
            normalized = url.rstrip("/").lower()
            if normalized not in seen:
                seen.add(normalized)
                unique.append(url)

        def sort_key(u):
            p = urlparse(u).path.lower()
            if "contact" in p:
                return 0
            if "about" in p:
                return 1
            if "team" in p:
                return 2
            return 3

        unique.sort(key=sort_key)
        return unique
