"""Clutch.co scraper — extracts company data from category listing pages."""

import re
import logging
from typing import Generator
from urllib.parse import urljoin, urlparse, parse_qs, unquote

from bs4 import BeautifulSoup

from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

# Maximum pages to scrape per category (safety limit)
MAX_PAGES = 100

# CSS selectors for Clutch.co — verified against known page structure.
# Clutch redesigns periodically; these may need updating.
SELECTORS = {
    "company_card": "li.provider-row, ul.providers__list > li.provider, div.provider-row",
    "company_name": "h3.provider__title a.provider__title-link, h3.company_info a, h3.provider__title a, a.company_name",
    "rating": "span.sg-rating__number, span.rating",
    "reviews_count": "a.sg-rating__reviews, a.reviews-link",
    "location": ".provider__highlights-item.location, span.locality, span.location",
    "website_link": "a.website-link__item, a.provider__cta-link",
    "min_project": ".field--field-pp-min-project-size .list-item__text, .custom_popover span",
    "hourly_rate": ".field--field-pp-hrly-rate-range .list-item__text, .custom_popover span",
    "employees": ".field--field-pp-size-people .list-item__text, .custom_popover span",
    "tagline": ".provider__tagline, .company_info__wrap .tagline",
    "services": ".provider__services-list-item, .services-list li",
    "next_page": "li.next a, a.page-link[rel='next'], .pager-next a",
}


class ClutchScraper(BaseScraper):
    """Scraper for Clutch.co service provider directories."""

    def get_total_companies(self) -> int | None:
        """Extract total company count from the page header."""
        try:
            html = self.get_page_content()
            # Clutch shows "X Companies" or "X Providers" in the header
            match = re.search(r"([\d,]+)\s+(?:Companies|Providers|Results)", html, re.IGNORECASE)
            if match:
                return int(match.group(1).replace(",", ""))
        except Exception as e:
            logger.warning("Could not extract total companies: %s", e)
        return None

    def scrape_category(self, url: str) -> Generator[dict, None, None]:
        """Scrape all companies from a Clutch.co category.

        Handles pagination automatically by following "next page" links.

        Args:
            url: Full category URL (e.g., https://clutch.co/developers).

        Yields:
            dict with keys: name, profile_url, rating, reviews_count, location,
            website_url, min_project, hourly_rate, employees, tagline, services, source.
        """
        current_url = url
        page_num = 0

        while current_url and page_num < MAX_PAGES:
            logger.info("Scraping page %d: %s", page_num, current_url)
            self.navigate(current_url, wait_until="domcontentloaded")

            # Wait for company cards to render
            try:
                self.page.wait_for_selector(
                    "li.provider-row, ul.providers__list > li, div.provider-row",
                    timeout=15000,
                )
            except Exception:
                logger.warning("No company cards found on page %d, stopping.", page_num)
                break

            # Scroll to load any lazy content
            self.scroll_page()

            html = self.get_page_content()
            soup = BeautifulSoup(html, "lxml")

            # Find company cards using multiple possible selectors
            cards = self._find_cards(soup)
            if not cards:
                logger.warning("No company cards parsed on page %d, stopping.", page_num)
                break

            logger.info("Found %d companies on page %d", len(cards), page_num)

            for card in cards:
                company = self._parse_company_card(card, url)
                if company and company.get("name"):
                    yield company

            # Get next page URL
            current_url = self._get_next_page_url(soup, url)
            page_num += 1

    def _find_cards(self, soup: BeautifulSoup) -> list:
        """Find company card elements using multiple selector strategies."""
        # Try each selector pattern
        for selector in SELECTORS["company_card"].split(", "):
            cards = soup.select(selector)
            if cards:
                return cards
        return []

    def _parse_company_card(self, card, base_url: str) -> dict | None:
        """Parse a single company card element into a data dict."""
        try:
            data = {
                "name": "",
                "profile_url": "",
                "rating": "",
                "reviews_count": "",
                "location": "",
                "website_url": "",
                "min_project": "",
                "hourly_rate": "",
                "employees": "",
                "tagline": "",
                "services": "",
                "email": "",  # Populated later by EmailExtractor
                "source": "Clutch.co",
            }

            # Company name and profile URL
            name_el = self._select_first(card, SELECTORS["company_name"])
            if name_el:
                data["name"] = name_el.get_text(strip=True)
                href = name_el.get("href", "")
                if href:
                    data["profile_url"] = urljoin("https://clutch.co", href)

            # Rating
            rating_el = self._select_first(card, SELECTORS["rating"])
            if rating_el:
                data["rating"] = rating_el.get_text(strip=True)

            # Reviews count
            reviews_el = self._select_first(card, SELECTORS["reviews_count"])
            if reviews_el:
                text = reviews_el.get_text(strip=True)
                match = re.search(r"(\d+)", text)
                if match:
                    data["reviews_count"] = match.group(1)

            # Location
            loc_el = self._select_first(card, SELECTORS["location"])
            if loc_el:
                data["location"] = loc_el.get_text(strip=True)

            # Website URL
            website_el = self._select_first(card, SELECTORS["website_link"])
            if website_el:
                href = website_el.get("href", "")
                if href and href.startswith("http"):
                    data["website_url"] = self._resolve_redirect_url(href)

            # Highlight items (min project, hourly rate, employees)
            # Clutch puts these in a highlights bar — try to extract from list items
            highlights = card.select(".list-item, .provider__highlights-item")
            for item in highlights:
                text = item.get_text(strip=True).lower()
                value = item.get_text(strip=True)
                if "$" in text and ("project" in text or "min" in text):
                    data["min_project"] = value
                elif "$" in text and ("hr" in text or "/" in text):
                    data["hourly_rate"] = value
                elif "employee" in text or re.search(r"\d+\s*[\-\+]\s*\d*", text):
                    if not data["employees"] and "$" not in text:
                        data["employees"] = value

            # Tagline
            tagline_el = self._select_first(card, SELECTORS["tagline"])
            if tagline_el:
                data["tagline"] = tagline_el.get_text(strip=True)

            # Services
            service_els = card.select(
                ".provider__services-list-item, .services-list li"
            )
            if service_els:
                services = [s.get_text(strip=True) for s in service_els]
                data["services"] = ", ".join(services)

            return data

        except Exception as e:
            logger.warning("Error parsing company card: %s", e)
            return None

    def _get_next_page_url(self, soup: BeautifulSoup, base_url: str) -> str | None:
        """Extract the next page URL from pagination."""
        for selector in SELECTORS["next_page"].split(", "):
            next_el = soup.select_one(selector)
            if next_el:
                href = next_el.get("href", "")
                if href:
                    return urljoin(base_url, href)
        return None

    @staticmethod
    def _resolve_redirect_url(url: str) -> str:
        """Extract the actual company URL from Clutch redirect URLs.

        Clutch wraps website links as https://r.clutch.co/redirect?...&u=<actual_url>.
        Returns the decoded actual URL, or the original URL if not a redirect.
        """
        try:
            parsed = urlparse(url)
            if "clutch.co" in parsed.netloc and "/redirect" in parsed.path:
                params = parse_qs(parsed.query)
                if "u" in params:
                    return unquote(params["u"][0])
        except Exception:
            pass
        return url

    @staticmethod
    def _select_first(element, selectors: str):
        """Try multiple comma-separated CSS selectors, return first match."""
        for selector in selectors.split(", "):
            result = element.select_one(selector.strip())
            if result:
                return result
        return None
