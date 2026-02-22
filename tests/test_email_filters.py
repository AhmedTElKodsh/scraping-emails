"""Comprehensive tests for config.email_filters module."""

import pytest
from config.email_filters import (
    is_valid_email,
    is_preferred_email,
    extract_emails_from_text,
    filter_and_rank_emails,
    BLOCKED_DOMAINS,
    BLOCKED_PREFIXES,
    ALLOWED_PREFIXES,
)


# ── is_valid_email ──────────────────────────────────────────────────────

class TestIsValidEmail:
    """Tests for the email validation function."""

    # Valid business emails
    @pytest.mark.parametrize("email", [
        "info@company.com",
        "hello@agency.io",
        "contact@firm.co.uk",
        "john@company.com",
        "sales@bigcorp.net",
        "admin@startup.dev",
        "jane.doe@company.com",
        "first.last@agency.org",
        "ceo@company.com",
        "marketing@brand.com",
        "hr@company.co",
    ])
    def test_valid_business_emails(self, email):
        assert is_valid_email(email) is True

    # Blocked prefix emails
    @pytest.mark.parametrize("email", [
        "noreply@company.com",
        "no-reply@company.com",
        "no_reply@company.com",
        "unsubscribe@company.com",
        "mailer-daemon@company.com",
        "postmaster@company.com",
        "bounce@company.com",
        "donotreply@company.com",
        "do-not-reply@company.com",
        "notifications@company.com",
        "alert@company.com",
        "automated@company.com",
    ])
    def test_blocked_prefix_emails(self, email):
        assert is_valid_email(email) is False

    # Blocked domain emails
    @pytest.mark.parametrize("email", [
        "user@sentry.io",
        "user@wixpress.com",
        "user@cloudflare.com",
        "user@example.com",
        "user@test.com",
        "user@googleapis.com",
        "user@google.com",
        "user@facebook.com",
        "user@mailchimp.com",
        "user@sendgrid.net",
        "user@shopify.com",
        "user@herokuapp.com",
    ])
    def test_blocked_domain_emails(self, email):
        assert is_valid_email(email) is False

    # File extension false positives
    @pytest.mark.parametrize("email", [
        "image.png@fake.com",
        "logo.jpg@company.com",
        "icon.svg@domain.com",
        "photo.jpeg@test.org",
        "banner.gif@site.com",
        "hero.webp@brand.net",
    ])
    def test_file_extension_emails_rejected(self, email):
        assert is_valid_email(email) is False

    # Too-short local part
    def test_single_char_local_part_rejected(self):
        assert is_valid_email("a@example.org") is False

    def test_two_char_local_part_accepted(self):
        assert is_valid_email("ab@company.com") is True

    # Malformed emails
    @pytest.mark.parametrize("email", [
        "",
        "not-an-email",
        "@nodomain.com",
        "noat.com",
        "user@",
        "user@.com",
        "user@com",
        "user name@company.com",
    ])
    def test_malformed_emails_rejected(self, email):
        assert is_valid_email(email) is False

    # Case insensitivity
    def test_case_insensitive_domain_check(self):
        assert is_valid_email("user@SENTRY.IO") is False

    def test_case_insensitive_prefix_check(self):
        assert is_valid_email("NoReply@company.com") is False

    def test_case_insensitive_valid(self):
        assert is_valid_email("INFO@COMPANY.COM") is True

    # Dotted blocked prefix (noreply.something)
    def test_dotted_blocked_prefix(self):
        assert is_valid_email("noreply.updates@company.com") is False

    def test_blocked_prefix_not_substring(self):
        # "alerts" should NOT be blocked (only "alert" is blocked prefix)
        # But "alert" as exact match IS blocked
        assert is_valid_email("alert@company.com") is False


# ── is_preferred_email ──────────────────────────────────────────────────

class TestIsPreferredEmail:
    """Tests for preferred email detection."""

    @pytest.mark.parametrize("email", [
        "info@company.com",
        "contact@company.com",
        "hello@agency.io",
        "sales@corp.net",
        "admin@startup.dev",
        "office@firm.com",
        "team@brand.com",
        "support@company.com",
        "enquiries@firm.co.uk",
        "inquiries@corp.com",
        "business@company.com",
        "general@corp.net",
        "mail@company.com",
    ])
    def test_preferred_emails(self, email):
        assert is_preferred_email(email) is True

    @pytest.mark.parametrize("email", [
        "john@company.com",
        "jane.doe@company.com",
        "ceo@company.com",
        "marketing@company.com",
        "hr@company.com",
        "dev@company.com",
    ])
    def test_non_preferred_emails(self, email):
        assert is_preferred_email(email) is False

    def test_dotted_prefix_is_preferred(self):
        # info.uk@company.com should match because "info" prefix with dot
        assert is_preferred_email("info.uk@company.com") is True


# ── extract_emails_from_text ────────────────────────────────────────────

class TestExtractEmailsFromText:
    """Tests for regex email extraction from text."""

    def test_single_email_in_text(self):
        text = "Contact us at info@company.com for more info."
        result = extract_emails_from_text(text)
        assert "info@company.com" in result

    def test_multiple_emails(self):
        text = "Email info@a.com or sales@b.com or support@c.com"
        result = extract_emails_from_text(text)
        assert len(result) == 3
        assert "info@a.com" in result
        assert "sales@b.com" in result
        assert "support@c.com" in result

    def test_no_emails(self):
        text = "This text has no email addresses at all."
        result = extract_emails_from_text(text)
        assert result == []

    def test_email_with_subdomains(self):
        text = "mail to user@sub.domain.co.uk"
        result = extract_emails_from_text(text)
        assert "user@sub.domain.co.uk" in result

    def test_email_with_plus(self):
        text = "test+tag@company.com"
        result = extract_emails_from_text(text)
        assert "test+tag@company.com" in result

    def test_email_with_dots_in_local(self):
        text = "first.middle.last@company.com"
        result = extract_emails_from_text(text)
        assert "first.middle.last@company.com" in result

    def test_empty_string(self):
        assert extract_emails_from_text("") == []


# ── filter_and_rank_emails ──────────────────────────────────────────────

class TestFilterAndRankEmails:
    """Tests for email filtering and ranking logic."""

    def test_preferred_email_wins(self):
        emails = ["john@company.com", "noreply@company.com", "info@company.com"]
        assert filter_and_rank_emails(emails) == "info@company.com"

    def test_all_blocked_returns_none(self):
        emails = ["noreply@company.com", "unsubscribe@company.com", "bounce@x.com"]
        assert filter_and_rank_emails(emails) is None

    def test_first_valid_non_preferred(self):
        emails = ["john@company.com", "jane@company.com"]
        assert filter_and_rank_emails(emails) == "john@company.com"

    def test_empty_list_returns_none(self):
        assert filter_and_rank_emails([]) is None

    def test_deduplication(self):
        emails = ["info@a.com", "INFO@A.COM", "info@a.com"]
        result = filter_and_rank_emails(emails)
        assert result == "info@a.com"

    def test_mixed_valid_and_invalid(self):
        emails = [
            "user@sentry.io",       # blocked domain
            "noreply@company.com",   # blocked prefix
            "image.png@fake.com",    # file extension
            "contact@real.com",      # valid + preferred
        ]
        assert filter_and_rank_emails(emails) == "contact@real.com"

    def test_single_valid_email(self):
        assert filter_and_rank_emails(["info@company.com"]) == "info@company.com"

    def test_non_preferred_returned_when_no_preferred(self):
        emails = ["john.doe@company.com"]
        assert filter_and_rank_emails(emails) == "john.doe@company.com"


# ── Allowlist/blocklist coverage ────────────────────────────────────────

class TestListCoverage:
    """Verify the configuration lists are properly populated."""

    def test_blocked_domains_not_empty(self):
        assert len(BLOCKED_DOMAINS) > 10

    def test_blocked_prefixes_not_empty(self):
        assert len(BLOCKED_PREFIXES) > 5

    def test_allowed_prefixes_not_empty(self):
        assert len(ALLOWED_PREFIXES) > 5

    def test_no_overlap_allowed_and_blocked(self):
        overlap = set(ALLOWED_PREFIXES) & set(BLOCKED_PREFIXES)
        assert overlap == set(), f"Overlap between allowed and blocked: {overlap}"
