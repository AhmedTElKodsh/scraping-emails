"""Comprehensive tests for extractors.email_extractor module.

Tests the email extraction logic using synthetic HTML — no live network calls.
"""

import pytest
from unittest.mock import MagicMock, patch
from bs4 import BeautifulSoup
from extractors.email_extractor import (
    EmailExtractor,
    CONTACT_PAGE_PATTERNS,
    CONTACT_LINK_TEXT,
)


# ── Fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def mock_page():
    """Create a mock Playwright page."""
    page = MagicMock()
    page.content.return_value = "<html><body></body></html>"
    page.goto.return_value = None
    page.wait_for_timeout.return_value = None
    return page


@pytest.fixture
def extractor(mock_page):
    return EmailExtractor(mock_page)


# ── _extract_best_email ─────────────────────────────────────────────────

class TestExtractBestEmail:
    def test_mailto_link(self, extractor):
        html = '<html><body><a href="mailto:info@company.com">Email us</a></body></html>'
        assert extractor._extract_best_email(html) == "info@company.com"

    def test_mailto_with_query_params(self, extractor):
        html = '<a href="mailto:hello@co.com?subject=Hi&body=Hello">Contact</a>'
        assert extractor._extract_best_email(html) == "hello@co.com"

    def test_email_in_text(self, extractor):
        html = "<html><body><p>Reach us at contact@firm.io anytime.</p></body></html>"
        assert extractor._extract_best_email(html) == "contact@firm.io"

    def test_prefers_preferred_email(self, extractor):
        html = """
        <body>
        <p>john.doe@company.com</p>
        <a href="mailto:info@company.com">Email</a>
        </body>
        """
        assert extractor._extract_best_email(html) == "info@company.com"

    def test_no_emails_returns_none(self, extractor):
        html = "<html><body><p>No email here at all.</p></body></html>"
        assert extractor._extract_best_email(html) is None

    def test_only_blocked_emails_returns_none(self, extractor):
        html = '<a href="mailto:noreply@company.com">Do not reply</a>'
        assert extractor._extract_best_email(html) is None

    def test_email_in_html_source_but_not_text(self, extractor):
        html = '<html><body><input value="hidden@company.com" type="hidden"></body></html>'
        # The regex runs on full HTML source too
        assert extractor._extract_best_email(html) == "hidden@company.com"

    def test_multiple_emails_returns_best(self, extractor):
        html = """
        <body>
        <p>random@sentry.io</p>
        <p>noreply@company.com</p>
        <p>sales@company.com</p>
        <p>ceo@company.com</p>
        </body>
        """
        # sales@ is preferred, sentry.io and noreply@ are blocked
        assert extractor._extract_best_email(html) == "sales@company.com"


# ── _find_contact_page_urls ─────────────────────────────────────────────

class TestFindContactPageUrls:
    def test_finds_contact_page(self, extractor):
        html = '<html><body><a href="/contact">Contact Us</a></body></html>'
        result = extractor._find_contact_page_urls(html, "https://company.com")
        assert "https://company.com/contact" in result

    def test_finds_about_page(self, extractor):
        html = '<a href="/about-us">About</a>'
        result = extractor._find_contact_page_urls(html, "https://company.com")
        assert any("about-us" in url for url in result)

    def test_finds_team_page(self, extractor):
        html = '<a href="/team">Our Team</a>'
        result = extractor._find_contact_page_urls(html, "https://company.com")
        assert any("team" in url for url in result)

    def test_finds_impressum(self, extractor):
        html = '<a href="/impressum">Impressum</a>'
        result = extractor._find_contact_page_urls(html, "https://company.com")
        assert any("impressum" in url for url in result)

    def test_finds_by_link_text(self, extractor):
        html = '<a href="/reach-out">Get in Touch</a>'
        result = extractor._find_contact_page_urls(html, "https://company.com")
        assert "https://company.com/reach-out" in result

    def test_ignores_external_links(self, extractor):
        html = '<a href="https://other.com/contact">Other Contact</a>'
        result = extractor._find_contact_page_urls(html, "https://company.com")
        assert len(result) == 0

    def test_ignores_hash_links(self, extractor):
        html = '<a href="#contact">Jump to Contact</a>'
        result = extractor._find_contact_page_urls(html, "https://company.com")
        assert len(result) == 0

    def test_ignores_javascript_links(self, extractor):
        html = '<a href="javascript:void(0)">Click</a>'
        result = extractor._find_contact_page_urls(html, "https://company.com")
        assert len(result) == 0

    def test_deduplicates_urls(self, extractor):
        html = """
        <a href="/contact">Contact 1</a>
        <a href="/contact/">Contact 2</a>
        """
        result = extractor._find_contact_page_urls(html, "https://company.com")
        assert len(result) == 1

    def test_contact_prioritized_over_about(self, extractor):
        html = """
        <a href="/about">About</a>
        <a href="/contact">Contact</a>
        <a href="/team">Team</a>
        """
        result = extractor._find_contact_page_urls(html, "https://company.com")
        assert result[0] == "https://company.com/contact"

    def test_resolves_relative_urls(self, extractor):
        html = '<a href="contact.html">Contact</a>'
        result = extractor._find_contact_page_urls(html, "https://company.com/pages/")
        assert result[0].startswith("https://company.com")

    def test_multilingual_contact_pages(self, extractor):
        html = """
        <a href="/kontakt">Kontakt</a>
        <a href="/contacto">Contacto</a>
        """
        result = extractor._find_contact_page_urls(html, "https://company.com")
        assert len(result) == 2


# ── find_email ──────────────────────────────────────────────────────────

class TestFindEmail:
    def test_invalid_url_returns_unreachable(self, extractor):
        assert extractor.find_email("") == "Unreachable"
        assert extractor.find_email("not-a-url") == "Unreachable"
        assert extractor.find_email(None) == "Unreachable"

    def test_email_found_on_landing_page(self, extractor, mock_page):
        mock_page.content.return_value = '<a href="mailto:info@acme-corp.com">Email</a>'
        result = extractor.find_email("https://acme-corp.com")
        assert result == "info@acme-corp.com"
        mock_page.goto.assert_called_once()

    def test_email_found_on_contact_page(self, extractor, mock_page):
        # Landing page has no email but has a contact link
        landing_html = '<html><body><a href="/contact">Contact</a></body></html>'
        contact_html = '<html><body><a href="mailto:hello@acme-corp.com">Email</a></body></html>'

        mock_page.content.side_effect = [landing_html, contact_html]
        result = extractor.find_email("https://acme-corp.com")
        assert result == "hello@acme-corp.com"
        assert mock_page.goto.call_count == 2

    def test_no_email_returns_unreachable(self, extractor, mock_page):
        mock_page.content.return_value = "<html><body>No emails here</body></html>"
        result = extractor.find_email("https://test.com")
        assert result == "Unreachable"

    def test_navigation_error_returns_unreachable(self, extractor, mock_page):
        mock_page.goto.side_effect = Exception("Timeout")
        result = extractor.find_email("https://unreachable.com")
        assert result == "Unreachable"

    def test_limits_contact_pages_to_3(self, extractor, mock_page):
        # Landing page with many contact-like links but no emails
        links = ''.join(f'<a href="/contact{i}">Contact {i}</a>' for i in range(10))
        no_email_html = f'<html><body>{links}</body></html>'
        mock_page.content.return_value = no_email_html

        extractor.find_email("https://test.com")
        # 1 landing + max 3 contact pages = 4 goto calls max
        assert mock_page.goto.call_count <= 4

    def test_ftp_url_returns_unreachable(self, extractor):
        assert extractor.find_email("ftp://files.company.com") == "Unreachable"


# ── Contact page patterns ───────────────────────────────────────────────

class TestContactPagePatterns:
    @pytest.mark.parametrize("path", [
        "/contact", "/Contact", "/CONTACT",
        "/kontakt", "/contacto", "/contato",
        "/about", "/about-us", "/a-propos", "/uber-uns",
        "/team", "/our-team", "/equipe",
        "/impressum", "/imprint", "/legal",
    ])
    def test_known_patterns_match(self, path):
        matched = any(p.search(path) for p in CONTACT_PAGE_PATTERNS)
        assert matched, f"Pattern should match: {path}"

    @pytest.mark.parametrize("path", [
        "/products", "/blog", "/pricing", "/services",
    ])
    def test_non_contact_paths_dont_match(self, path):
        matched = any(p.search(path) for p in CONTACT_PAGE_PATTERNS)
        assert not matched, f"Pattern should NOT match: {path}"


class TestContactLinkText:
    @pytest.mark.parametrize("text", [
        "Contact", "contact us", "About", "about us",
        "Team", "our team", "Get in Touch", "Reach Us",
        "Impressum", "Imprint",
    ])
    def test_known_text_matches(self, text):
        assert CONTACT_LINK_TEXT.search(text) is not None

    @pytest.mark.parametrize("text", [
        "Products", "Blog", "Pricing", "Login",
    ])
    def test_non_contact_text_doesnt_match(self, text):
        assert CONTACT_LINK_TEXT.search(text) is None
