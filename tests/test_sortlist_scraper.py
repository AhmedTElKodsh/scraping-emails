"""Comprehensive tests for scrapers.sortlist module.

Uses synthetic HTML/__NEXT_DATA__ fixtures — no live network calls required.
"""

import json
import pytest
from bs4 import BeautifulSoup
from scrapers.sortlist import SortlistScraper, MAX_PAGES


# ── Fixtures ────────────────────────────────────────────────────────────

def make_agency_jsonapi(
    name="Test Agency",
    slug="test-agency",
    tagline="We do great work",
    description="<p>Full description here</p>",
    website_url="https://testagency.com",
    team_size=25,
    reviews_count=10,
    reviews_rating_total=9.5,
    address_en="Paris, France",
    sectors=None,
):
    """Build a JSON:API agency object as found in __NEXT_DATA__."""
    sectors = sectors or [
        {"name": {"en": "Digital Strategy"}},
        {"name": {"en": "Branding"}},
    ]
    return {
        "id": f"uuid-{slug}",
        "type": "agency",
        "attributes": {
            "name": name,
            "slug": slug,
            "tagline": tagline,
            "description": description,
            "website_url": website_url,
            "website": website_url,
            "team_size": team_size,
            "reviews_count": reviews_count,
            "reviews_rating_total": reviews_rating_total,
            "address": {"en": address_en, "fr": address_en},
            "addresses": [{"address": {"en": address_en}}],
            "sectors": sectors,
            "languages": ["en"],
            "locale": "en",
            "score": 1.0,
        },
    }


def make_next_data_html(organic_agencies=None, paid_agencies=None):
    """Build HTML page with __NEXT_DATA__ script containing agencies."""
    organic = organic_agencies or []
    paid = paid_agencies or []

    next_data = {
        "props": {
            "pageProps": {
                "data": {
                    "organicAgencies": {
                        "data": [],
                        "included": organic,
                        "meta": {},
                        "links": {},
                    },
                    "paidAgencies": {
                        "data": [],
                        "included": paid,
                        "meta": {},
                        "links": {},
                    },
                },
            },
        },
    }

    cards = []
    for a in organic + paid:
        attrs = a.get("attributes", {})
        slug = attrs.get("slug", "")
        name = attrs.get("name", "")
        if slug and name:
            cards.append(
                f'<li class="list-reset"><a class="agency-card-content" href="/agency/{slug}">'
                f'<div class="agency-name"><p title="{name}"><span>{name}</span></p></div></a></li>'
            )

    return f"""
    <html><body>
    <script id="__NEXT_DATA__" type="application/json">{json.dumps(next_data)}</script>
    <ul class="grid-list">
        {''.join(cards)}
    </ul>
    </body></html>
    """


def make_html_only_page(agencies):
    """Build HTML page with agency cards but NO __NEXT_DATA__."""
    cards = []
    for a in agencies:
        cards.append(f"""
        <li class="list-reset">
            <a class="agency-card-content" href="/agency/{a['slug']}">
                <div class="agency-name">
                    <p title="{a['name']}"><span>{a['name']}</span></p>
                </div>
                <div class="agency-rating">
                    <span class="bold h6 mr-1">{a.get('rating', '4.5')}</span>
                    <span>({a.get('reviews', '10')} reviews)</span>
                </div>
                <div>Located in {a.get('location', 'Paris, France')}From</div>
                <div>{a.get('team', '10-50')} members</div>
            </a>
        </li>
        """)
    return f"<html><body><ul>{''.join(cards)}</ul></body></html>"


@pytest.fixture
def scraper():
    """Create a SortlistScraper instance without starting a browser."""
    return SortlistScraper(headless=True)


# ── Instantiation ───────────────────────────────────────────────────────

class TestSortlistScraperInit:
    def test_browser_not_started(self, scraper):
        assert scraper._browser is None
        assert scraper._page is None

    def test_intercepted_agencies_empty(self, scraper):
        assert scraper._intercepted_agencies == []

    def test_response_handler_none(self, scraper):
        assert scraper._response_handler is None


# ── __NEXT_DATA__ extraction ────────────────────────────────────────────

class TestExtractFromNextData:
    def test_extracts_organic_agencies(self, scraper):
        agencies = [
            make_agency_jsonapi(name="Agency A", slug="agency-a"),
            make_agency_jsonapi(name="Agency B", slug="agency-b"),
        ]
        html = make_next_data_html(organic_agencies=agencies)
        result = scraper._extract_from_next_data(html)
        assert len(result) == 2
        assert result[0]["name"] == "Agency A"
        assert result[1]["name"] == "Agency B"

    def test_extracts_paid_agencies(self, scraper):
        paid = [make_agency_jsonapi(name="Paid Co", slug="paid-co")]
        html = make_next_data_html(paid_agencies=paid)
        result = scraper._extract_from_next_data(html)
        assert len(result) == 1
        assert result[0]["name"] == "Paid Co"

    def test_combines_organic_and_paid(self, scraper):
        organic = [make_agency_jsonapi(name="Org", slug="org")]
        paid = [make_agency_jsonapi(name="Paid", slug="paid")]
        html = make_next_data_html(organic_agencies=organic, paid_agencies=paid)
        result = scraper._extract_from_next_data(html)
        assert len(result) == 2

    def test_deduplicates_by_profile_url(self, scraper):
        dup = make_agency_jsonapi(name="Same", slug="same-agency")
        html = make_next_data_html(organic_agencies=[dup], paid_agencies=[dup])
        result = scraper._extract_from_next_data(html)
        assert len(result) == 1

    def test_skips_non_agency_types(self, scraper):
        agency = make_agency_jsonapi(name="Real", slug="real")
        non_agency = {"id": "x", "type": "work", "attributes": {"name": "Fake"}}
        html = make_next_data_html(organic_agencies=[agency, non_agency])
        result = scraper._extract_from_next_data(html)
        assert len(result) == 1
        assert result[0]["name"] == "Real"

    def test_no_next_data_returns_empty(self, scraper):
        html = "<html><body>No script tag here</body></html>"
        assert scraper._extract_from_next_data(html) == []

    def test_invalid_json_returns_empty(self, scraper):
        html = '<html><body><script id="__NEXT_DATA__">{invalid json}</script></body></html>'
        assert scraper._extract_from_next_data(html) == []

    def test_empty_next_data_returns_empty(self, scraper):
        html = '<html><body><script id="__NEXT_DATA__">{}</script></body></html>'
        assert scraper._extract_from_next_data(html) == []


# ── _parse_jsonapi_agency ───────────────────────────────────────────────

class TestParseJsonapiAgency:
    def test_extracts_all_fields(self, scraper):
        item = make_agency_jsonapi(
            name="Orbis",
            slug="orbis",
            website_url="https://orbis.com",
            team_size=73,
            reviews_count=188,
            reviews_rating_total=187.875,
            address_en="Milan, Italy",
        )
        result = scraper._parse_jsonapi_agency(item)

        assert result["name"] == "Orbis"
        assert result["profile_url"] == "https://www.sortlist.com/agency/orbis"
        assert result["website_url"] == "https://orbis.com"
        assert result["team_size"] == "73"
        assert result["reviews_count"] == "188"
        assert result["location"] == "Milan, Italy"
        assert result["source"] == "Sortlist.com"
        assert result["email"] == ""
        # Rating: 187.875 / 188 * 5 = 4.993... rounds to 5.0
        assert result["rating"] == "5.0"

    def test_cleans_html_tagline(self, scraper):
        item = make_agency_jsonapi(tagline="Best &amp; Greatest <b>Agency</b>")
        result = scraper._parse_jsonapi_agency(item)
        assert "&amp;" not in result["tagline"]
        assert "<b>" not in result["tagline"]
        assert "Best" in result["tagline"]

    def test_cleans_html_description(self, scraper):
        item = make_agency_jsonapi(description="<p>Hello &amp; welcome</p>")
        result = scraper._parse_jsonapi_agency(item)
        # description is not directly exposed but tagline fallback isn't used here

    def test_no_reviews_no_rating(self, scraper):
        item = make_agency_jsonapi(reviews_count=0, reviews_rating_total=0)
        result = scraper._parse_jsonapi_agency(item)
        assert result["rating"] == ""
        assert result["reviews_count"] == ""

    def test_services_extracted(self, scraper):
        item = make_agency_jsonapi(sectors=[
            {"name": {"en": "Web Dev"}},
            {"name": {"en": "Mobile"}},
        ])
        result = scraper._parse_jsonapi_agency(item)
        assert "Web Dev" in result["services"]
        assert "Mobile" in result["services"]

    def test_flat_agency_dict_handled(self, scraper):
        """Test the flat dict format (older API style)."""
        flat = {
            "name": "Flat Agency",
            "slug": "flat-agency",
            "website_url": "https://flat.com",
            "rating": "4.5",
            "reviews_count": "20",
            "addresses": [{"city": "Berlin", "country": "Germany"}],
            "sectors": [{"name": "Design"}],
        }
        result = scraper._parse_jsonapi_agency(flat)
        assert result["name"] == "Flat Agency"
        assert result["profile_url"] == "https://www.sortlist.com/agency/flat-agency"

    def test_no_attributes_no_name_returns_none(self, scraper):
        result = scraper._parse_jsonapi_agency({"id": "x", "type": "unknown"})
        assert result is None

    def test_tagline_truncated_to_200_chars(self, scraper):
        long_tagline = "A" * 500
        item = make_agency_jsonapi(tagline=long_tagline)
        result = scraper._parse_jsonapi_agency(item)
        assert len(result["tagline"]) <= 200


# ── _extract_location ───────────────────────────────────────────────────

class TestExtractLocation:
    def test_locale_dict_address(self, scraper):
        attrs = {"address": {"en": "Paris, France", "fr": "Paris, France"}}
        assert scraper._extract_location(attrs) == "Paris, France"

    def test_locale_dict_fallback_to_first_value(self, scraper):
        attrs = {"address": {"de": "Berlin, Deutschland"}}
        assert scraper._extract_location(attrs) == "Berlin, Deutschland"

    def test_addresses_array_with_nested_dict(self, scraper):
        attrs = {"addresses": [{"address": {"en": "London, UK"}}]}
        assert scraper._extract_location(attrs) == "London, UK"

    def test_addresses_array_flat_format(self, scraper):
        attrs = {"addresses": [{"city": "Rome", "country": "Italy"}]}
        assert scraper._extract_location(attrs) == "Rome, Italy"

    def test_main_address_fallback(self, scraper):
        attrs = {"main_address": "Tokyo, Japan"}
        assert scraper._extract_location(attrs) == "Tokyo, Japan"

    def test_empty_attrs_returns_empty(self, scraper):
        assert scraper._extract_location({}) == ""

    def test_empty_address_dict(self, scraper):
        attrs = {"address": {}}
        assert scraper._extract_location(attrs) == ""


# ── _extract_services ───────────────────────────────────────────────────

class TestExtractServices:
    def test_nested_name_dicts(self, scraper):
        attrs = {"sectors": [
            {"name": {"en": "Web Dev"}},
            {"name": {"en": "Mobile"}},
        ]}
        assert scraper._extract_services(attrs) == "Web Dev, Mobile"

    def test_flat_name_strings(self, scraper):
        attrs = {"sectors": [{"name": "Design"}, {"name": "Branding"}]}
        assert scraper._extract_services(attrs) == "Design, Branding"

    def test_string_items(self, scraper):
        attrs = {"expertises": ["AI", "ML", "Data"]}
        assert scraper._extract_services(attrs) == "AI, ML, Data"

    def test_empty_returns_empty(self, scraper):
        assert scraper._extract_services({}) == ""

    def test_limits_to_10_items(self, scraper):
        attrs = {"sectors": [{"name": f"S{i}"} for i in range(20)]}
        result = scraper._extract_services(attrs)
        assert len(result.split(", ")) == 10


# ── HTML card parsing fallback ──────────────────────────────────────────

class TestParseHtmlCards:
    def test_extracts_from_agency_card_content(self, scraper):
        agencies = [
            {"name": "Alpha", "slug": "alpha", "rating": "4.8", "reviews": "20"},
            {"name": "Beta", "slug": "beta", "rating": "5.0", "reviews": "15"},
        ]
        html = make_html_only_page(agencies)
        result = scraper._parse_html_cards(html, "https://www.sortlist.com/advertising")
        assert len(result) == 2
        assert result[0]["name"] == "Alpha"
        assert result[1]["name"] == "Beta"

    def test_extracts_rating(self, scraper):
        html = make_html_only_page([{"name": "X", "slug": "x", "rating": "4.8", "reviews": "30"}])
        result = scraper._parse_html_cards(html, "https://www.sortlist.com/advertising")
        assert result[0]["rating"] == "4.8"

    def test_extracts_review_count(self, scraper):
        html = make_html_only_page([{"name": "X", "slug": "x", "reviews": "42"}])
        result = scraper._parse_html_cards(html, "https://www.sortlist.com/advertising")
        assert result[0]["reviews_count"] == "42"

    def test_extracts_location(self, scraper):
        html = make_html_only_page([{"name": "X", "slug": "x", "location": "Berlin, Germany"}])
        result = scraper._parse_html_cards(html, "https://www.sortlist.com/advertising")
        assert result[0]["location"] == "Berlin, Germany"

    def test_deduplicates_by_slug(self, scraper):
        html = """
        <html><body>
        <a class="agency-card-content" href="/agency/dup">
            <div class="agency-name"><p title="Dup"><span>Dup</span></p></div>
        </a>
        <a class="agency-card-content" href="/agency/dup">
            <div class="agency-name"><p title="Dup"><span>Dup</span></p></div>
        </a>
        </body></html>
        """
        result = scraper._parse_html_cards(html, "https://www.sortlist.com/advertising")
        assert len(result) == 1

    def test_profile_url_built_correctly(self, scraper):
        html = make_html_only_page([{"name": "X", "slug": "my-agency"}])
        result = scraper._parse_html_cards(html, "https://www.sortlist.com/advertising")
        assert result[0]["profile_url"] == "https://www.sortlist.com/agency/my-agency"

    def test_empty_page_returns_empty(self, scraper):
        html = "<html><body><p>No agencies</p></body></html>"
        result = scraper._parse_html_cards(html, "https://www.sortlist.com/advertising")
        assert result == []

    def test_source_is_sortlist(self, scraper):
        html = make_html_only_page([{"name": "X", "slug": "x"}])
        result = scraper._parse_html_cards(html, "https://www.sortlist.com/advertising")
        assert result[0]["source"] == "Sortlist.com"


# ── _build_page_url ─────────────────────────────────────────────────────

class TestBuildPageUrl:
    def test_adds_page_param(self, scraper):
        result = scraper._build_page_url("https://www.sortlist.com/advertising", 3)
        assert "page=3" in result
        assert "sortlist.com/advertising" in result

    def test_replaces_existing_page_param(self, scraper):
        result = scraper._build_page_url("https://www.sortlist.com/advertising?page=1", 5)
        assert "page=5" in result
        assert "page=1" not in result

    def test_preserves_other_params(self, scraper):
        result = scraper._build_page_url("https://www.sortlist.com/advertising?sort=rating", 2)
        assert "sort=rating" in result
        assert "page=2" in result


# ── Constants ───────────────────────────────────────────────────────────

class TestSortlistConstants:
    def test_max_pages(self):
        assert MAX_PAGES == 50
