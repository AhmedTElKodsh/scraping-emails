"""Sortlist.com scraper — extracts company data from __NEXT_DATA__, API, or HTML."""

import json
import re
import logging
from typing import Generator
from urllib.parse import urljoin, urlparse, parse_qs, urlencode

from bs4 import BeautifulSoup

from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

# Maximum pages to scrape per category (safety limit)
MAX_PAGES = 50


class SortlistScraper(BaseScraper):
    """Scraper for Sortlist.com service provider directories.

    Primary strategy: extract structured agency data from the __NEXT_DATA__
    script tag (server-side rendered JSON). Sortlist embeds all agency info
    in this tag as JSON:API format with 'included' agency objects.

    Secondary strategy: intercept XHR/Fetch API responses for dynamic page loads.

    Fallback strategy: parse rendered HTML using stable semantic class names
    (agency-name, agency-rating, etc.) on the card elements.
    """

    def __init__(self, headless: bool | str = True, proxy_server: str = ""):
        super().__init__(headless, proxy_server)
        self._intercepted_agencies: list[dict] = []
        self._response_handler = None

    def get_total_companies(self) -> int | None:
        """Extract total company count from the page."""
        try:
            html = self.get_page_content()
            match = re.search(r"([\d,]+)\s+(?:agencies|providers|companies|results)", html, re.IGNORECASE)
            if match:
                return int(match.group(1).replace(",", ""))
        except Exception as e:
            logger.warning("Could not extract total companies: %s", e)
        return None

    def scrape_category(self, url: str, start_page: int = 1) -> Generator[dict, None, None]:
        """Scrape all companies from a Sortlist.com category.

        Tries __NEXT_DATA__ extraction first, then API interception, then HTML parsing.
        Handles pagination by incrementing ?page=N.

        Args:
            url: Full category URL (e.g., https://www.sortlist.com/advertising).
            start_page: Page number to start from (1-indexed, default 1).

        Yields:
            dict with keys: name, profile_url, rating, reviews_count, location,
            website_url, team_size, tagline, services, email, source.
        """
        # Register API interception handler once
        self._setup_api_interception()

        page_num = max(1, start_page)
        empty_pages = 0

        while page_num <= MAX_PAGES:
            current_url = self._build_page_url(url, page_num) if page_num > 1 else url
            logger.info("Scraping page %d: %s", page_num, current_url)

            # Clear intercepted data for this page
            self._intercepted_agencies = []

            self.navigate(current_url, wait_until="domcontentloaded")

            # Wait for agency cards to render
            try:
                self.page.wait_for_selector(
                    "a[href*='/agency/']",
                    timeout=20000,
                )
            except Exception:
                logger.warning("No agency links found on page %d after wait.", page_num)

            self.random_delay(2.0, 4.0)
            self.scroll_page()

            html = self.get_page_content()
            companies_found = 0

            # Strategy 1: Parse __NEXT_DATA__ JSON (most reliable)
            next_data_companies = self._extract_from_next_data(html)
            if next_data_companies:
                logger.info("Extracted %d agencies from __NEXT_DATA__ on page %d", len(next_data_companies), page_num)
                for company in next_data_companies:
                    if company.get("name"):
                        companies_found += 1
                        yield company

            # Strategy 2: API interception (for client-side navigations)
            if companies_found == 0 and self._intercepted_agencies:
                logger.info("Intercepted %d agencies from API on page %d", len(self._intercepted_agencies), page_num)
                for agency_data in self._intercepted_agencies:
                    company = self._parse_jsonapi_agency(agency_data)
                    if company and company.get("name"):
                        companies_found += 1
                        yield company

            # Strategy 3: Parse HTML with semantic class selectors
            if companies_found == 0:
                logger.info("Falling back to HTML card parsing on page %d", page_num)
                parsed = self._parse_html_cards(html, url)
                for company in parsed:
                    if company.get("name"):
                        companies_found += 1
                        yield company

            # Stop if no companies found on this page
            if companies_found == 0:
                empty_pages += 1
                if empty_pages >= 2:
                    logger.info("Two consecutive empty pages, stopping pagination.")
                    break
            else:
                empty_pages = 0

            page_num += 1

    # ── Strategy 1: __NEXT_DATA__ extraction ────────────────────────────

    def _extract_from_next_data(self, html: str) -> list[dict]:
        """Extract agency data from the __NEXT_DATA__ script tag.

        Sortlist embeds all page data as server-rendered JSON in a script tag.
        The agencies are in pageProps.data.organicAgencies and paidAgencies,
        using JSON:API format with 'included' arrays containing full agency objects.
        """
        soup = BeautifulSoup(html, "lxml")
        script = soup.find("script", id="__NEXT_DATA__")
        if not script or not script.string:
            return []

        try:
            data = json.loads(script.string)
        except (json.JSONDecodeError, TypeError):
            logger.debug("Failed to parse __NEXT_DATA__ JSON")
            return []

        page_props = data.get("props", {}).get("pageProps", {})
        if not isinstance(page_props, dict):
            return []
        pp_data = page_props.get("data", {})
        if not isinstance(pp_data, dict):
            return []

        companies = []

        # Extract from both organic and paid agency lists
        for list_key in ("organicAgencies", "paidAgencies"):
            agency_container = pp_data.get(list_key, {})
            if not isinstance(agency_container, dict):
                continue

            # JSON:API format: 'included' has full agency objects
            included = agency_container.get("included", [])
            if isinstance(included, list):
                for item in included:
                    if isinstance(item, dict) and item.get("type") == "agency":
                        company = self._parse_jsonapi_agency(item)
                        if company:
                            companies.append(company)

        # Deduplicate by slug/profile_url
        seen = set()
        unique = []
        for c in companies:
            key = c.get("profile_url", "")
            if key and key not in seen:
                seen.add(key)
                unique.append(c)

        return unique

    def _parse_jsonapi_agency(self, item: dict) -> dict | None:
        """Parse a JSON:API agency object from __NEXT_DATA__ or API response.

        The 'included' items have format:
            {
                "id": "uuid",
                "type": "agency",
                "attributes": {
                    "description": "...",
                    "name": "...",
                    "slug": "...",
                    "tagline": "...",
                    "team_members_count": 15,
                    "website_url": "...",
                    ...
                },
                "relationships": { ... }
            }

        Also handles flat dict format from API interception where fields are at top level.
        """
        # JSON:API format (from __NEXT_DATA__)
        attrs = item.get("attributes", {})
        if attrs and isinstance(attrs, dict):
            name = attrs.get("name", "")
            slug = attrs.get("slug", "")
            tagline = attrs.get("tagline", "") or ""
            description = attrs.get("description", "") or ""
            website_url = attrs.get("website_url", "") or attrs.get("website", "") or ""
            team_size = attrs.get("team_size", "") or attrs.get("team_members_count", "")

            # Clean HTML entities and tags from description/tagline
            if tagline and ("&" in tagline or "<" in tagline):
                tagline = BeautifulSoup(tagline, "lxml").get_text(strip=True)
            if description and ("&" in description or "<" in description):
                description = BeautifulSoup(description, "lxml").get_text(strip=True)

            # Extract location from addresses in attributes
            location = self._extract_location(attrs)

            # Extract rating and review count
            rating = ""
            reviews_count = ""
            rc = attrs.get("reviews_count", 0)
            rt = attrs.get("reviews_rating_total", 0)
            if rc:
                reviews_count = str(rc)
                if rt and rc > 0:
                    avg = round(rt / rc * 5, 1)  # rating_total is normalized 0-1, scale to 5
                    rating = str(avg)

            # Extract services/expertises
            services = self._extract_services(attrs)

            profile_url = f"https://www.sortlist.com/agency/{slug}" if slug else ""

            return {
                "name": name,
                "profile_url": profile_url,
                "rating": rating,
                "reviews_count": reviews_count,
                "location": location,
                "website_url": website_url,
                "team_size": str(team_size) if team_size else "",
                "tagline": tagline[:200] if tagline else "",
                "services": services,
                "email": "",
                "source": "Sortlist.com",
            }

        # Flat format (from older API interception)
        if "name" in item or "slug" in item:
            return self._parse_flat_agency(item)

        return None

    def _parse_flat_agency(self, data: dict) -> dict:
        """Parse a flat agency dict (older API format)."""
        location = ""
        addresses = data.get("addresses", [])
        if addresses and isinstance(addresses, list):
            addr = addresses[0]
            if isinstance(addr, dict):
                parts = [addr.get("city", ""), addr.get("country", "")]
                location = ", ".join(p for p in parts if p)

        services = ""
        sectors = data.get("sectors", [])
        if sectors and isinstance(sectors, list):
            service_names = []
            for s in sectors[:10]:
                if isinstance(s, dict):
                    name = s.get("name", "") or s.get("en", "") or s.get("label", "")
                    if isinstance(name, dict):
                        name = name.get("en", "") or next(iter(name.values()), "")
                    if name:
                        service_names.append(str(name))
                elif isinstance(s, str):
                    service_names.append(s)
            services = ", ".join(service_names)

        slug = data.get("slug", "")
        profile_url = f"https://www.sortlist.com/agency/{slug}" if slug else ""

        return {
            "name": data.get("name", ""),
            "profile_url": profile_url,
            "rating": str(data.get("reviews_rating_total", data.get("rating", ""))),
            "reviews_count": str(data.get("reviews_count", "")),
            "location": location,
            "website_url": data.get("website_url", data.get("website", "")),
            "team_size": str(data.get("team_size", "")),
            "tagline": data.get("tagline", data.get("description", ""))[:200],
            "services": services,
            "email": "",
            "source": "Sortlist.com",
        }

    def _extract_location(self, attrs: dict) -> str:
        """Extract location string from various nested formats."""
        # Try 'address' dict (locale-keyed, e.g., {"en": "Milan, Italy", "fr": "Milan, Italie"})
        address = attrs.get("address", {})
        if isinstance(address, dict):
            loc = address.get("en", "") or next(iter(address.values()), "")
            if loc:
                return str(loc)

        # Try addresses array (list of dicts with nested 'address' locale dicts)
        addresses = attrs.get("addresses", [])
        if isinstance(addresses, list) and addresses:
            addr = addresses[0]
            if isinstance(addr, dict):
                nested = addr.get("address", {})
                if isinstance(nested, dict):
                    loc = nested.get("en", "") or next(iter(nested.values()), "")
                    if loc:
                        return str(loc)
                # Flat format fallback
                parts = [addr.get("city", ""), addr.get("country", "")]
                loc = ", ".join(p for p in parts if p)
                if loc:
                    return loc

        # Try main_address or locality
        main_addr = attrs.get("main_address", "") or attrs.get("locality", "")
        if main_addr:
            return str(main_addr)

        return ""

    def _extract_services(self, attrs: dict) -> str:
        """Extract services/expertises from various nested formats."""
        # Try expertises array
        for key in ("expertises", "services", "sectors"):
            items = attrs.get(key, [])
            if isinstance(items, list) and items:
                names = []
                for item in items[:10]:
                    if isinstance(item, dict):
                        name = (
                            item.get("name", "")
                            or item.get("expertise_name", "")
                            or item.get("label", "")
                        )
                        # Handle nested translations like {"en": "Digital Strategy"}
                        if isinstance(name, dict):
                            name = name.get("en", "") or next(iter(name.values()), "")
                        if name:
                            names.append(str(name))
                    elif isinstance(item, str):
                        names.append(item)
                if names:
                    return ", ".join(names)
        return ""

    # ── Strategy 2: API interception ─────────────────────────────────────

    def _setup_api_interception(self) -> None:
        """Register a response handler to capture API data. Called once."""
        if self._response_handler is not None:
            return

        def handle_response(response):
            try:
                url = response.url
                if ("/_next/data/" in url or "/api/" in url) and response.status == 200:
                    content_type = response.headers.get("content-type", "")
                    if "json" in content_type:
                        body = response.json()
                        self._extract_agencies_from_api(body)
            except Exception as e:
                logger.debug("Skipping non-JSON response %s: %s", response.url, e)

        self._response_handler = handle_response
        self.page.on("response", handle_response)

    def _extract_agencies_from_api(self, data, depth: int = 0) -> None:
        """Recursively search API JSON response for agency data."""
        if depth > 5:
            return

        if isinstance(data, dict):
            if "pageProps" in data:
                self._extract_agencies_from_api(data["pageProps"], depth + 1)
                return

            # Check for JSON:API 'included' array with agency objects
            included = data.get("included", [])
            if isinstance(included, list):
                for item in included:
                    if isinstance(item, dict) and item.get("type") == "agency":
                        self._intercepted_agencies.append(item)
                if self._intercepted_agencies:
                    return

            # Look for flat agency lists
            for key in ("agencies", "providers", "results", "hits", "items", "data"):
                if key in data and isinstance(data[key], list):
                    items = data[key]
                    if items and isinstance(items[0], dict) and ("name" in items[0] or "slug" in items[0]):
                        for item in items:
                            if isinstance(item, dict) and ("name" in item or "slug" in item):
                                self._intercepted_agencies.append(item)
                        return

            for value in data.values():
                if isinstance(value, (dict, list)):
                    self._extract_agencies_from_api(value, depth + 1)

        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and ("name" in item or "slug" in item):
                    self._intercepted_agencies.append(item)
                elif isinstance(item, (dict, list)):
                    self._extract_agencies_from_api(item, depth + 1)

    # ── Strategy 3: HTML card parsing ────────────────────────────────────

    def _parse_html_cards(self, html: str, base_url: str) -> list[dict]:
        """Fallback: parse rendered HTML using stable semantic class names.

        Sortlist uses hashed CSS classes for styling, but agency card elements
        use stable semantic classes like 'agency-name', 'agency-rating', etc.
        """
        soup = BeautifulSoup(html, "lxml")
        companies = []

        # Agency cards are <a> tags with class 'agency-card-content' inside <li>
        cards = soup.select("a.agency-card-content")
        if not cards:
            # Fallback: find all links to agency profiles
            cards = soup.find_all("a", href=re.compile(r"/agency/[a-z0-9\-]+"))

        seen_slugs = set()
        for card in cards:
            href = card.get("href", "")
            if "/agency/" not in href:
                continue

            slug = href.rstrip("/").split("/")[-1]
            if slug in seen_slugs:
                continue
            seen_slugs.add(slug)

            company = {
                "name": "",
                "profile_url": urljoin(base_url, href),
                "rating": "",
                "reviews_count": "",
                "location": "",
                "website_url": "",
                "team_size": "",
                "tagline": "",
                "services": "",
                "email": "",
                "source": "Sortlist.com",
            }

            # Name: from <p> with title attribute inside .agency-name, or <img alt>
            name_p = card.select_one(".agency-name p[title]")
            if name_p:
                company["name"] = name_p.get("title", "").strip()
            else:
                # Try img alt on the logo
                logo = card.select_one("img.agency-logo")
                if logo:
                    company["name"] = logo.get("alt", "").strip()

            # Rating: <span> inside .agency-rating
            rating_span = card.select_one(".agency-rating span.bold")
            if rating_span:
                company["rating"] = rating_span.get_text(strip=True)

            # Review count: text matching "(\d+) review"
            rating_div = card.select_one(".agency-rating")
            if rating_div:
                rating_text = rating_div.get_text()
                review_match = re.search(r"\((\d+)\s+review", rating_text)
                if review_match:
                    company["reviews_count"] = review_match.group(1)

            # Location: look for text after "Located in"
            card_text = card.get_text()
            loc_match = re.search(r"Located\s+in\s*(.+?)(?:From|Budget|Worked|$)", card_text)
            if loc_match:
                location = loc_match.group(1).strip()
                # Clean up trailing content
                location = re.split(r"\(?\+\d", location)[0].strip()
                company["location"] = location

            # Team size: look for "X-Y members" or "X members"
            team_match = re.search(r"(\d[\d,\-+\s]+member)", card_text, re.IGNORECASE)
            if team_match:
                company["team_size"] = team_match.group(1).strip()

            if company["name"]:
                companies.append(company)

        return companies

    # ── Helpers ──────────────────────────────────────────────────────────

    def _build_page_url(self, base_url: str, page_num: int) -> str:
        """Build the URL for a specific page number."""
        parsed = urlparse(base_url)
        params = parse_qs(parsed.query)
        params["page"] = [str(page_num)]
        new_query = urlencode(params, doseq=True)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{new_query}"
