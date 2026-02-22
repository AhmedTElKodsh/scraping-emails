"""Email validation and filtering rules."""

import re

# Prefixes we WANT to capture (common business contact emails)
ALLOWED_PREFIXES = [
    "info",
    "hello",
    "contact",
    "sales",
    "admin",
    "office",
    "team",
    "support",
    "enquiries",
    "inquiries",
    "business",
    "general",
    "mail",
]

# Prefixes we REJECT (automated/system emails)
BLOCKED_PREFIXES = [
    "noreply",
    "no-reply",
    "no_reply",
    "unsubscribe",
    "mailer-daemon",
    "postmaster",
    "bounce",
    "donotreply",
    "do-not-reply",
    "notifications",
    "alert",
    "automated",
]

# Domains we REJECT (platform/service emails, not the company's own)
BLOCKED_DOMAINS = [
    "sentry.io",
    "wixpress.com",
    "cloudflare.com",
    "example.com",
    "test.com",
    "localhost",
    "googleapis.com",
    "google.com",
    "facebook.com",
    "twitter.com",
    "github.com",
    "amazonaws.com",
    "mailchimp.com",
    "sendgrid.net",
    "mailgun.org",
    "hubspot.com",
    "zendesk.com",
    "intercom.io",
    "crisp.chat",
    "tawk.to",
    "freshdesk.com",
    "wordpress.com",
    "squarespace.com",
    "wix.com",
    "shopify.com",
    "webflow.io",
    "herokuapp.com",
    "netlify.app",
    "vercel.app",
    "pages.dev",
]

# File extensions that indicate an image/asset path, not an email
BLOCKED_EXTENSIONS = [".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".bmp"]

# Regex pattern for extracting email addresses
EMAIL_REGEX = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
)


def is_valid_email(email: str) -> bool:
    """Check if an email passes our allowlist/blocklist filters.

    Returns True if the email looks like a legitimate business contact email.
    """
    email = email.lower().strip()

    # Basic format check
    if not EMAIL_REGEX.fullmatch(email):
        return False

    local_part, domain = email.rsplit("@", 1)

    # Reject if domain is in blocked list
    if domain in BLOCKED_DOMAINS:
        return False

    # Reject if local part matches blocked prefix
    for prefix in BLOCKED_PREFIXES:
        if local_part == prefix or local_part.startswith(prefix + "."):
            return False

    # Reject if it looks like a file path (contains image extension)
    for ext in BLOCKED_EXTENSIONS:
        if ext in email:
            return False

    # Reject very short or suspicious local parts
    if len(local_part) < 2:
        return False

    return True


def is_preferred_email(email: str) -> bool:
    """Check if email has a preferred business prefix (info@, contact@, etc.).

    Used to prioritize among multiple valid emails.
    """
    local_part = email.lower().split("@")[0]
    return any(local_part == prefix or local_part.startswith(prefix + ".") for prefix in ALLOWED_PREFIXES)


def extract_emails_from_text(text: str) -> list[str]:
    """Extract all email-like strings from text."""
    return EMAIL_REGEX.findall(text)


def filter_and_rank_emails(emails: list[str]) -> str | None:
    """Filter emails and return the best one, or None.

    Priority:
    1. Preferred prefix emails (info@, contact@, etc.)
    2. Any other valid email
    """
    valid = [e for e in emails if is_valid_email(e)]
    if not valid:
        return None

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for e in valid:
        lower = e.lower()
        if lower not in seen:
            seen.add(lower)
            unique.append(e)

    # Prefer business contact emails
    preferred = [e for e in unique if is_preferred_email(e)]
    if preferred:
        return preferred[0]

    return unique[0]
