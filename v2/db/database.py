"""SQLite database for storing scraped company data.

Schema:
  - companies: one row per unique company (deduped by profile_url)
  - company_categories: many-to-many junction (company <-> service/field)
  - scrape_progress: tracks which categories have been scraped (enables resume)
"""

import sqlite3
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "companies.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    profile_url TEXT,
    rating REAL,
    reviews_count INTEGER,
    location TEXT,
    country TEXT,
    website_url TEXT,
    min_project TEXT,
    hourly_rate TEXT,
    employees TEXT,
    team_size TEXT,
    tagline TEXT,
    services TEXT,
    source TEXT NOT NULL,
    email TEXT,
    contact_form_url TEXT,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_companies_profile_url
    ON companies(profile_url) WHERE profile_url IS NOT NULL AND profile_url != '';

CREATE INDEX IF NOT EXISTS idx_companies_source ON companies(source);
CREATE INDEX IF NOT EXISTS idx_companies_country ON companies(country);
CREATE INDEX IF NOT EXISTS idx_companies_rating ON companies(rating);
CREATE INDEX IF NOT EXISTS idx_companies_email ON companies(email);
CREATE INDEX IF NOT EXISTS idx_companies_name ON companies(name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_companies_website ON companies(website_url);

CREATE TABLE IF NOT EXISTS company_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    service TEXT NOT NULL,
    field TEXT NOT NULL,
    source TEXT NOT NULL,
    UNIQUE(company_id, service, field, source)
);

CREATE INDEX IF NOT EXISTS idx_cc_service ON company_categories(service);
CREATE INDEX IF NOT EXISTS idx_cc_field ON company_categories(field);
CREATE INDEX IF NOT EXISTS idx_cc_company_id ON company_categories(company_id);

CREATE TABLE IF NOT EXISTS scrape_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    service TEXT NOT NULL,
    field TEXT NOT NULL,
    url TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    pages_scraped INTEGER DEFAULT 0,
    companies_found INTEGER DEFAULT 0,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    UNIQUE(source, service, field)
);
"""


def _extract_country(location: str) -> str:
    """Extract country from location string.

    Examples:
      "New York, NY" -> "United States"
      "Milan, Italy" -> "Italy"
      "London, United Kingdom" -> "United Kingdom"
    """
    if not location:
        return ""
    parts = [p.strip() for p in location.split(",")]
    if not parts:
        return ""
    last = parts[-1]
    # 2-letter US state code -> "United States"
    if len(last) == 2 and last.isalpha() and last.isupper():
        return "United States"
    return last


class Database:
    """SQLite database wrapper for company data."""

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> None:
        self._conn = sqlite3.connect(str(self.db_path), timeout=30, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(SCHEMA_SQL)
        self._conn.commit()
        logger.info("Database connected: %s", self.db_path)

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._conn

    # ── Company CRUD ─────────────────────────────────────────────────

    def upsert_company(self, data: dict) -> int:
        """Insert or update a company, returning company_id.

        Uses profile_url as the dedup key.
        """
        profile_url = data.get("profile_url", "")
        if not profile_url:
            return self._insert_company(data)

        row = self.conn.execute(
            "SELECT id FROM companies WHERE profile_url = ?", (profile_url,)
        ).fetchone()

        if row:
            company_id = row["id"]
            self._update_company_fields(company_id, data)
            return company_id
        else:
            return self._insert_company(data)

    def _insert_company(self, data: dict) -> int:
        location = data.get("location", "")
        country = _extract_country(location)
        rating = self._parse_float(data.get("rating", ""))
        reviews = self._parse_int(data.get("reviews_count", ""))

        cursor = self.conn.execute(
            """INSERT INTO companies
               (name, profile_url, rating, reviews_count, location, country,
                website_url, min_project, hourly_rate, employees, team_size,
                tagline, services, source, email, contact_form_url)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data.get("name", ""),
                data.get("profile_url", ""),
                rating, reviews, location, country,
                data.get("website_url", ""),
                data.get("min_project", ""),
                data.get("hourly_rate", ""),
                data.get("employees", ""),
                data.get("team_size", ""),
                data.get("tagline", ""),
                data.get("services", ""),
                data.get("source", ""),
                data.get("email", ""),
                data.get("contact_form_url", ""),
            ),
        )
        self.conn.commit()
        return cursor.lastrowid

    def _update_company_fields(self, company_id: int, data: dict) -> None:
        updates = []
        params = []
        field_map = {
            "name": "name", "rating": "rating", "reviews_count": "reviews_count",
            "location": "location", "website_url": "website_url",
            "min_project": "min_project", "hourly_rate": "hourly_rate",
            "employees": "employees", "team_size": "team_size",
            "tagline": "tagline", "services": "services",
        }
        for data_key, col in field_map.items():
            value = data.get(data_key, "")
            if value:
                if col == "rating":
                    value = self._parse_float(value)
                elif col == "reviews_count":
                    value = self._parse_int(value)
                updates.append(f"{col} = ?")
                params.append(value)
        location = data.get("location", "")
        if location:
            updates.append("country = ?")
            params.append(_extract_country(location))
        if updates:
            params.append(company_id)
            self.conn.execute(
                f"UPDATE companies SET {', '.join(updates)} WHERE id = ?", params
            )
            self.conn.commit()

    def add_category(self, company_id: int, service: str, field: str, source: str) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO company_categories (company_id, service, field, source) VALUES (?, ?, ?, ?)",
            (company_id, service, field, source),
        )
        self.conn.commit()

    def update_email(self, company_id: int, email: str, contact_form_url: str = "") -> None:
        self.conn.execute(
            "UPDATE companies SET email = ?, contact_form_url = ? WHERE id = ?",
            (email, contact_form_url, company_id),
        )
        self.conn.commit()

    def get_pending_email_companies(self) -> list[dict]:
        rows = self.conn.execute(
            """SELECT id, name, website_url FROM companies
               WHERE website_url IS NOT NULL AND website_url != ''
               AND (email IS NULL OR email = '')
               ORDER BY id"""
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Scrape progress ──────────────────────────────────────────────

    def init_scrape_tasks(self, tasks: list[tuple[str, str, str, str]]) -> None:
        """Populate scrape_progress. tasks: [(source, service, field, url)]."""
        for source, service, field, url in tasks:
            self.conn.execute(
                "INSERT OR IGNORE INTO scrape_progress (source, service, field, url, status) VALUES (?, ?, ?, ?, 'pending')",
                (source, service, field, url),
            )
        self.conn.execute("UPDATE scrape_progress SET status = 'pending' WHERE status = 'in_progress'")
        self.conn.commit()

    def get_pending_tasks(self) -> list[dict]:
        """Return tasks not yet fully completed (pending, failed, or paused between batches)."""
        rows = self.conn.execute(
            "SELECT source, service, field, url, pages_scraped FROM scrape_progress WHERE status IN ('pending', 'failed') ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_batch_tasks(self) -> list[dict]:
        """Return tasks that need another batch (batch_done status)."""
        rows = self.conn.execute(
            "SELECT source, service, field, url, pages_scraped FROM scrape_progress WHERE status = 'batch_done' ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_resumable_tasks(self) -> list[dict]:
        """Return all tasks that aren't fully completed (pending + failed + batch_done)."""
        rows = self.conn.execute(
            "SELECT source, service, field, url, pages_scraped FROM scrape_progress WHERE status IN ('pending', 'failed', 'batch_done') ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]

    def mark_task_in_progress(self, source: str, service: str, field: str) -> None:
        self.conn.execute(
            "UPDATE scrape_progress SET status = 'in_progress', started_at = ? WHERE source = ? AND service = ? AND field = ?",
            (datetime.now().isoformat(), source, service, field),
        )
        self.conn.commit()

    def mark_task_batch_done(self, source: str, service: str, field: str,
                             pages_scraped: int, companies: int) -> None:
        """Mark a category as having completed a batch (more pages remain)."""
        self.conn.execute(
            """UPDATE scrape_progress
               SET status = 'batch_done', pages_scraped = ?,
                   companies_found = companies_found + ?
               WHERE source = ? AND service = ? AND field = ?""",
            (pages_scraped, companies, source, service, field),
        )
        self.conn.commit()

    def mark_task_completed(self, source: str, service: str, field: str, companies: int) -> None:
        self.conn.execute(
            """UPDATE scrape_progress
               SET status = 'completed', completed_at = ?,
                   companies_found = companies_found + ?
               WHERE source = ? AND service = ? AND field = ?""",
            (datetime.now().isoformat(), companies, source, service, field),
        )
        self.conn.commit()

    def mark_task_failed(self, source: str, service: str, field: str, error: str) -> None:
        self.conn.execute(
            "UPDATE scrape_progress SET status = 'failed', error_message = ? WHERE source = ? AND service = ? AND field = ?",
            (error, source, service, field),
        )
        self.conn.commit()

    def get_scrape_progress(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM scrape_progress ORDER BY source, service, field").fetchall()
        return [dict(r) for r in rows]

    # ── Search / filter queries ──────────────────────────────────────

    def search_companies(
        self,
        source: str | None = None,
        service: str | None = None,
        field: str | None = None,
        country: str | None = None,
        min_rating: float | None = None,
        max_rating: float | None = None,
        has_email: bool | None = None,
        name_search: str | None = None,
        email_processed: bool | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """Search with filters. Returns (rows, total_count)."""
        where_clauses = []
        params = []

        if email_processed is True:
            where_clauses.append("c.email IS NOT NULL AND c.email != ''")
        if source:
            where_clauses.append("c.source = ?")
            params.append(source)
        if service:
            where_clauses.append("EXISTS (SELECT 1 FROM company_categories cc WHERE cc.company_id = c.id AND cc.service = ?)")
            params.append(service)
        if field:
            where_clauses.append("EXISTS (SELECT 1 FROM company_categories cc WHERE cc.company_id = c.id AND cc.field = ?)")
            params.append(field)
        if country:
            where_clauses.append("c.country = ?")
            params.append(country)
        if min_rating is not None:
            where_clauses.append("c.rating >= ?")
            params.append(min_rating)
        if max_rating is not None:
            where_clauses.append("c.rating <= ?")
            params.append(max_rating)
        if has_email is True:
            where_clauses.append("c.email IS NOT NULL AND c.email != '' AND c.email != 'Unreachable'")
        elif has_email is False:
            where_clauses.append("(c.email IS NULL OR c.email = '' OR c.email = 'Unreachable')")
        if name_search:
            where_clauses.append("c.name LIKE ?")
            params.append(f"%{name_search}%")

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        total = self.conn.execute(f"SELECT COUNT(*) FROM companies c WHERE {where_sql}", params).fetchone()[0]

        data_sql = f"""
            SELECT c.*,
                   GROUP_CONCAT(DISTINCT cc.service) AS category,
                   GROUP_CONCAT(DISTINCT cc.field) AS sub_category
            FROM companies c
            LEFT JOIN company_categories cc ON cc.company_id = c.id
            WHERE {where_sql}
            GROUP BY c.id
            ORDER BY c.rating DESC NULLS LAST, c.reviews_count DESC NULLS LAST
            LIMIT ? OFFSET ?
        """
        rows = self.conn.execute(data_sql, params + [limit, offset]).fetchall()
        return [dict(r) for r in rows], total

    def get_all_countries(self) -> list[str]:
        rows = self.conn.execute(
            "SELECT DISTINCT country FROM companies WHERE country IS NOT NULL AND country != '' ORDER BY country"
        ).fetchall()
        return [r["country"] for r in rows]

    def get_all_services(self) -> list[str]:
        rows = self.conn.execute("SELECT DISTINCT service FROM company_categories ORDER BY service").fetchall()
        return [r["service"] for r in rows]

    def get_fields_for_service(self, service: str) -> list[str]:
        rows = self.conn.execute(
            "SELECT DISTINCT field FROM company_categories WHERE service = ? ORDER BY field", (service,)
        ).fetchall()
        return [r["field"] for r in rows]

    def get_stats(self) -> dict:
        total = self.conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
        with_email = self.conn.execute(
            "SELECT COUNT(*) FROM companies WHERE email IS NOT NULL AND email != '' AND email != 'Unreachable'"
        ).fetchone()[0]
        with_contact_form = self.conn.execute(
            "SELECT COUNT(*) FROM companies WHERE contact_form_url IS NOT NULL AND contact_form_url != ''"
        ).fetchone()[0]
        clutch = self.conn.execute("SELECT COUNT(*) FROM companies WHERE source = 'Clutch.co'").fetchone()[0]
        sortlist = self.conn.execute("SELECT COUNT(*) FROM companies WHERE source = 'Sortlist.com'").fetchone()[0]
        return {
            "total": total, "with_email": with_email, "with_contact_form": with_contact_form,
            "clutch_count": clutch, "sortlist_count": sortlist,
        }

    @staticmethod
    def _parse_float(value) -> float | None:
        if not value:
            return None
        try:
            return float(str(value).strip())
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_int(value) -> int | None:
        if not value:
            return None
        try:
            return int(str(value).strip().replace(",", ""))
        except (ValueError, TypeError):
            return None
