"""Comprehensive tests for scrapers.clutch module.

Uses synthetic HTML fixtures — no live network calls required.
"""

import pytest
from bs4 import BeautifulSoup
from scrapers.clutch import ClutchScraper, SELECTORS, MAX_PAGES


# ── Fixtures ────────────────────────────────────────────────────────────

def make_card_html(
    name="Test Company",
    profile_href="/profile/test-company",
    rating="4.5",
    reviews="42 Reviews",
    location="New York, NY",
    website_href="https://testcompany.com",
    tagline="We build great software",
    services=None,
    employees="50 - 249",
):
    """Build a synthetic Clutch company card HTML."""
    services = services or ["Web Development", "Mobile App Development"]
    services_html = "".join(f'<li class="provider__services-list-item">{s}</li>' for s in services)

    return f"""
    <div class="provider-row">
        <h3 class="provider__title">
            <a class="provider__title-link" href="{profile_href}">{name}</a>
        </h3>
        <span class="sg-rating__number">{rating}</span>
        <a class="sg-rating__reviews">{reviews}</a>
        <div class="provider__highlights-item location">{location}</div>
        <a class="website-link__item" href="{website_href}">Visit Website</a>
        <div class="provider__highlights-item">
            <span>{employees}</span>
        </div>
        <div class="provider__tagline">{tagline}</div>
        <ul>{services_html}</ul>
    </div>
    """


def make_page_html(cards_html, next_page_href=None):
    """Wrap card HTML in a page-like structure."""
    next_link = ""
    if next_page_href:
        next_link = f'<li class="next"><a href="{next_page_href}">Next</a></li>'
    return f"""
    <html><body>
    <h1>1,234 Companies</h1>
    {cards_html}
    <ul class="pager">{next_link}</ul>
    </body></html>
    """


@pytest.fixture
def scraper():
    """Create a ClutchScraper instance without starting a browser."""
    return ClutchScraper(headless=True)


# ── Instantiation ───────────────────────────────────────────────────────

class TestClutchScraperInit:
    def test_browser_not_started(self, scraper):
        assert scraper._browser is None
        assert scraper._page is None

    def test_headless_stored(self):
        s = ClutchScraper(headless="virtual")
        assert s.headless == "virtual"

    def test_page_property_raises_without_browser(self, scraper):
        with pytest.raises(RuntimeError, match="Browser not started"):
            _ = scraper.page


# ── _resolve_redirect_url ───────────────────────────────────────────────

class TestResolveRedirectUrl:
    def test_clutch_redirect_extracts_actual_url(self):
        redirect = "https://r.clutch.co/redirect?ref=123&u=https%3A%2F%2Fwww.realcompany.com%2F"
        result = ClutchScraper._resolve_redirect_url(redirect)
        assert result == "https://www.realcompany.com/"

    def test_non_redirect_url_unchanged(self):
        url = "https://www.company.com"
        assert ClutchScraper._resolve_redirect_url(url) == url

    def test_other_domain_redirect_unchanged(self):
        url = "https://other.com/redirect?u=https://target.com"
        assert ClutchScraper._resolve_redirect_url(url) == url

    def test_redirect_without_u_param(self):
        url = "https://r.clutch.co/redirect?ref=123&other=value"
        assert ClutchScraper._resolve_redirect_url(url) == url

    def test_encoded_url_decoded(self):
        redirect = "https://r.clutch.co/redirect?u=https%3A%2F%2Fcompany.com%2Fpage%3Fq%3D1%26lang%3Den"
        result = ClutchScraper._resolve_redirect_url(redirect)
        assert result == "https://company.com/page?q=1&lang=en"

    def test_empty_string(self):
        assert ClutchScraper._resolve_redirect_url("") == ""

    def test_malformed_url(self):
        assert ClutchScraper._resolve_redirect_url("not-a-url") == "not-a-url"


# ── _select_first ───────────────────────────────────────────────────────

class TestSelectFirst:
    def test_finds_first_matching_selector(self):
        html = '<div><span class="a">first</span><span class="b">second</span></div>'
        soup = BeautifulSoup(html, "lxml")
        result = ClutchScraper._select_first(soup, "span.a, span.b")
        assert result.get_text() == "first"

    def test_fallback_to_second_selector(self):
        html = '<div><span class="b">only-b</span></div>'
        soup = BeautifulSoup(html, "lxml")
        result = ClutchScraper._select_first(soup, "span.a, span.b")
        assert result.get_text() == "only-b"

    def test_returns_none_when_no_match(self):
        html = '<div><span class="c">none</span></div>'
        soup = BeautifulSoup(html, "lxml")
        result = ClutchScraper._select_first(soup, "span.a, span.b")
        assert result is None


# ── _find_cards ─────────────────────────────────────────────────────────

class TestFindCards:
    def test_finds_provider_row_divs(self, scraper):
        html = '<div class="provider-row">A</div><div class="provider-row">B</div>'
        soup = BeautifulSoup(html, "lxml")
        cards = scraper._find_cards(soup)
        assert len(cards) == 2

    def test_finds_li_provider_row(self, scraper):
        html = '<li class="provider-row">A</li>'
        soup = BeautifulSoup(html, "lxml")
        cards = scraper._find_cards(soup)
        assert len(cards) == 1

    def test_empty_page_returns_empty(self, scraper):
        html = '<div class="no-companies">Nothing here</div>'
        soup = BeautifulSoup(html, "lxml")
        cards = scraper._find_cards(soup)
        assert cards == []


# ── _parse_company_card ─────────────────────────────────────────────────

class TestParseCompanyCard:
    def test_extracts_all_fields(self, scraper):
        card_html = make_card_html()
        soup = BeautifulSoup(card_html, "lxml")
        card = soup.select_one("div.provider-row")
        result = scraper._parse_company_card(card, "https://clutch.co/developers")

        assert result["name"] == "Test Company"
        assert result["profile_url"] == "https://clutch.co/profile/test-company"
        assert result["rating"] == "4.5"
        assert result["reviews_count"] == "42"
        assert result["location"] == "New York, NY"
        assert result["website_url"] == "https://testcompany.com"
        assert result["tagline"] == "We build great software"
        assert "Web Development" in result["services"]
        assert "Mobile App Development" in result["services"]
        assert result["source"] == "Clutch.co"
        assert result["email"] == ""  # populated later

    def test_redirect_url_resolved(self, scraper):
        card_html = make_card_html(
            website_href="https://r.clutch.co/redirect?u=https%3A%2F%2Factual.com"
        )
        soup = BeautifulSoup(card_html, "lxml")
        card = soup.select_one("div.provider-row")
        result = scraper._parse_company_card(card, "https://clutch.co/developers")
        assert result["website_url"] == "https://actual.com"

    def test_missing_website(self, scraper):
        card_html = make_card_html(website_href="")
        soup = BeautifulSoup(card_html, "lxml")
        card = soup.select_one("div.provider-row")
        result = scraper._parse_company_card(card, "https://clutch.co/developers")
        assert result["website_url"] == ""

    def test_missing_rating(self, scraper):
        html = """
        <div class="provider-row">
            <h3 class="provider__title"><a class="provider__title-link" href="/p/x">NoRating Co</a></h3>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        card = soup.select_one("div.provider-row")
        result = scraper._parse_company_card(card, "https://clutch.co/developers")
        assert result["name"] == "NoRating Co"
        assert result["rating"] == ""

    def test_reviews_extracts_number_only(self, scraper):
        card_html = make_card_html(reviews="156 Reviews on Clutch")
        soup = BeautifulSoup(card_html, "lxml")
        card = soup.select_one("div.provider-row")
        result = scraper._parse_company_card(card, "https://clutch.co/developers")
        assert result["reviews_count"] == "156"


# ── _get_next_page_url ──────────────────────────────────────────────────

class TestGetNextPageUrl:
    def test_finds_next_page(self, scraper):
        html = '<ul><li class="next"><a href="/developers?page=2">Next</a></li></ul>'
        soup = BeautifulSoup(html, "lxml")
        result = scraper._get_next_page_url(soup, "https://clutch.co/developers")
        assert result == "https://clutch.co/developers?page=2"

    def test_no_next_page_returns_none(self, scraper):
        html = '<ul><li class="prev"><a href="/developers?page=1">Prev</a></li></ul>'
        soup = BeautifulSoup(html, "lxml")
        result = scraper._get_next_page_url(soup, "https://clutch.co/developers")
        assert result is None

    def test_relative_href_resolved(self, scraper):
        html = '<ul><li class="next"><a href="?page=3">Next</a></li></ul>'
        soup = BeautifulSoup(html, "lxml")
        result = scraper._get_next_page_url(soup, "https://clutch.co/developers")
        assert "page=3" in result

    def test_empty_href_returns_none(self, scraper):
        html = '<ul><li class="next"><a href="">Next</a></li></ul>'
        soup = BeautifulSoup(html, "lxml")
        result = scraper._get_next_page_url(soup, "https://clutch.co/developers")
        assert result is None


# ── Constants ───────────────────────────────────────────────────────────

class TestConstants:
    def test_max_pages_is_reasonable(self):
        assert MAX_PAGES == 100

    def test_selectors_has_required_keys(self):
        required = ["company_card", "company_name", "rating", "reviews_count",
                     "location", "website_link", "next_page"]
        for key in required:
            assert key in SELECTORS, f"Missing selector: {key}"
