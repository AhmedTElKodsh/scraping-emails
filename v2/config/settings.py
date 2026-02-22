"""Central config loader — reads from .env file at project root."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (works regardless of where script is invoked from)
_PROJECT_ROOT = Path(__file__).parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env", override=False)


def _get(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


# ── Email ─────────────────────────────────────────────────────────
EMAIL_TO: str = _get("EMAIL_TO")
EMAIL_FROM: str = _get("EMAIL_FROM")
EMAIL_PASSWORD: str = _get("EMAIL_PASSWORD")

# ── Scraper ───────────────────────────────────────────────────────
PROXY_URL: str = _get("PROXY_URL")
MAX_PAGES: int = int(_get("MAX_PAGES", "10"))
BATCH_INTERVAL_HOURS: float = float(_get("BATCH_INTERVAL_HOURS", "2"))

# ── Paths ─────────────────────────────────────────────────────────
DB_PATH: str = _get("DB_PATH", "data/companies.db")
OUTPUT_DIR: str = _get("OUTPUT_DIR", "data")

# ── Browser ───────────────────────────────────────────────────────
BROWSER_ENGINE: str = _get("BROWSER_ENGINE", "playwright")
