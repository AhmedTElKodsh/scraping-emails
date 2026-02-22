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
    "company_card": "div.provider-row, li.provider-row, ul.providers__list > li.provider",
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
    "next_page": "a.sg-pagination-v2-next:not(.sg-pagination-v2-disabled), li.next a, a.page-link[rel='next'], .pager-next a",
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

    def scrape_category(self, url: str, start_page: int = 0) -> Generator[dict, None, None]:
        """Scrape all companies from a Clutch.co category.

        Handles pagination automatically by following "next page" links.

        Args:
            url: Full category URL (e.g., https://clutch.co/developers).
            start_page: Page number to start from (0-indexed, default 0).

        Yields:
            dict with keys: name, profile_url, rating, reviews_count, location,
            website_url, min_project, hourly_rate, employees, tagline, services, source.
        """
        # Build start URL — Clutch supports ?page=N for direct access
        if start_page > 0:
            sep = "&" if "?" in url else "?"
            current_url = f"{url}{sep}page={start_page}"
        else:
            current_url = url
        page_num = start_page

        while current_url and page_num < MAX_PAGES:
            logger.info("Scraping page %d: %s", page_num, current_url)
            self.navigate(current_url, wait_until="domcontentloaded")

            # Extra wait for JS-rendered content
            self.page.wait_for_timeout(3000)

            # Wait for company cards to render — try multiple selectors
            card_found = False
            for selector in [
                "div.provider-row",
                "li.provider-row",
                "ul.providers__list > li",
                "[data-provider]",
                ".directory-list .provider",
            ]:
                try:
                    self.page.wait_for_selector(selector, timeout=5000)
                    card_found = True
                    logger.info("Found cards with selector: %s", selector)
                    break
                except Exception:
                    continue

            if not card_found:
                logger.warning("No company cards found on page %d, stopping.", page_num)
                # Log page title for debugging
                try:
                    title = self.page.title()
                    logger.warning("Page title was: %s", title)
                except Exception:
                    pass
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
                    profile_url = urljoin("https://clutch.co", href)
                    # Sponsored listings wrap the name link in tracking URLs.
                    # Try to find the real /profile/... link in the card instead.
                    if "r.clutch.co/redirect" in profile_url or "ppc.clutch.co" in profile_url:
                        real_link = self._find_real_profile_link(card)
                        if real_link:
                            profile_url = real_link
                    data["profile_url"] = profile_url

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
    def _find_real_profile_link(card) -> str | None:
        """Scan all <a> tags in a card for the real /profile/... URL."""
        for a_tag in card.find_all("a", href=True):
            href = a_tag["href"]
            if "/profile/" in href and "r.clutch.co" not in href and "ppc.clutch.co" not in href:
                return urljoin("https://clutch.co", href)
        return None

    @staticmethod
    def _resolve_redirect_url(url: str) -> str:
        """Extract the actual company URL from Clutch redirect/PPC URLs.

        Clutch wraps website links as https://r.clutch.co/redirect?...&u=<actual_url>.
        Returns the decoded actual URL, or the original URL if not a redirect.
        Also handles ppc.clutch.co tracking links.
        """
        try:
            parsed = urlparse(url)
            if "clutch.co" in parsed.netloc and "/redirect" in parsed.path:
                params = parse_qs(parsed.query)
                if "u" in params:
                    resolved = unquote(params["u"][0])
                    # The u= param may itself be a ppc.clutch.co link — skip those
                    if "ppc.clutch.co" not in resolved:
                        return resolved
            # ppc.clutch.co links are tracking URLs with no real destination
            if "ppc.clutch.co" in url:
                return ""
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
