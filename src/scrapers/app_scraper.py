"""One-shot API scraper for app.farida.estate (Layer 2).

Requires:
  1. Completed API recon (data/api_contract.json populated)
  2. Credentials in .env (FARIDA_EMAIL, FARIDA_PASSWORD)
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.auth.token_auth_manager import TokenAuthManager as AuthManager
from src.storage.database import (
    get_connection, init_db,
    log_scrape_start, log_scrape_end,
)

REQUEST_DELAY = 3  # seconds between requests


def load_dotenv_simple():
    """Load .env file without external dependency."""
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip())


def create_app_tables(conn, endpoints):
    """Dynamically create tables based on discovered API endpoints.

    Each endpoint gets a table with: id, raw_json, scraped_at.
    The raw_json stores the complete response for later analysis.
    """
    for ep in endpoints:
        table_name = f"app_{ep['name']}"
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS "{table_name}" (
                id TEXT PRIMARY KEY,
                data_json TEXT NOT NULL,
                scraped_at TEXT NOT NULL
            )
        """)
    conn.commit()


def scrape_endpoint(auth, conn, ep_config):
    """Scrape a single API endpoint with pagination."""
    name = ep_config["name"]
    url = ep_config["url"]
    method = ep_config.get("method", "GET").upper()
    table_name = f"app_{name}"

    pagination = ep_config.get("pagination", {})
    pag_type = pagination.get("type", "none")

    run_id = log_scrape_start(conn, "app", name)
    total_items = 0
    errors = 0

    print(f"\n{'='*60}")
    print(f"  Scraping: {name} ({url})")
    print(f"{'='*60}")

    try:
        page = 1
        cursor = None

        while True:
            params = {}
            if pag_type == "page":
                pag_params = pagination.get("params", ["page", "limit"])
                params[pag_params[0]] = page
                if len(pag_params) > 1:
                    params[pag_params[1]] = pagination.get("per_page", 20)
            elif pag_type == "cursor" and cursor:
                cursor_param = pagination.get("cursor_param", "cursor")
                params[cursor_param] = cursor
            elif pag_type == "offset":
                params["offset"] = (page - 1) * pagination.get("per_page", 20)
                params["limit"] = pagination.get("per_page", 20)

            print(f"  Page {page}...", end=" ", flush=True)

            if method == "GET":
                resp = auth.get(url, params=params)
            else:
                resp = auth.post(url, json_body=params)

            if resp.status_code != 200:
                print(f"HTTP {resp.status_code}")
                errors += 1
                break

            try:
                data = resp.json()
            except ValueError:
                print("Invalid JSON")
                errors += 1
                break

            # Extract items from response — handle common wrapper patterns
            items = data
            if isinstance(data, dict):
                items = (
                    data.get("data")
                    or data.get("results")
                    or data.get("items")
                    or data.get("records")
                    or [data]
                )

            if not isinstance(items, list):
                items = [items]

            if not items:
                print("Empty response.")
                break

            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).isoformat()

            for item in items:
                item_id = str(
                    item.get("id")
                    or item.get("_id")
                    or item.get("uuid")
                    or hash(json.dumps(item, sort_keys=True))
                )
                try:
                    conn.execute(f"""
                        INSERT INTO "{table_name}" (id, data_json, scraped_at)
                        VALUES (?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                            data_json=excluded.data_json,
                            scraped_at=excluded.scraped_at
                    """, (item_id, json.dumps(item), now))
                    total_items += 1
                except Exception as e:
                    print(f"\n    Error storing item {item_id}: {e}")
                    errors += 1

            conn.commit()
            print(f"{len(items)} items")

            # Check if we should continue pagination
            if pag_type == "none":
                break
            elif pag_type == "cursor":
                cursor = data.get("next_cursor") or data.get("nextCursor")
                if not cursor:
                    break
            elif pag_type in ("page", "offset"):
                total_available = (
                    data.get("total")
                    or data.get("totalCount")
                    or data.get("meta", {}).get("total")
                )
                if total_available and total_items >= total_available:
                    break
                if len(items) < pagination.get("per_page", 20):
                    break

            page += 1
            time.sleep(REQUEST_DELAY)

        log_scrape_end(conn, run_id, total_items, errors)
        print(f"  Result: {total_items} items, {errors} errors")

    except Exception as e:
        log_scrape_end(conn, run_id, total_items, errors, "failed", str(e))
        print(f"  FAILED: {e}")
        raise

    return total_items, errors


def run_one_shot():
    """Execute one-shot extraction of all app.farida.estate data."""
    load_dotenv_simple()

    print("\n" + "=" * 60)
    print("  APP.FARIDA.ESTATE — One-Shot API Extraction (Layer 2)")
    print("=" * 60)

    contract_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "data", "api_contract.json"
    )

    try:
        auth = AuthManager(contract_path)
    except ValueError as e:
        print(f"\n  ERROR: {e}")
        print("  Please complete the API recon first.")
        print("  See: src/recon/RECON_GUIDE.md")
        return

    endpoints = auth.contract.get("endpoints", [])
    if not endpoints:
        print("\n  No endpoints configured in api_contract.json")
        print("  Complete the recon and add endpoints to the contract.")
        return

    conn = get_connection()
    init_db(conn)
    create_app_tables(conn, endpoints)

    # Login
    try:
        auth.login()
    except Exception as e:
        print(f"\n  Login failed: {e}")
        return

    grand_total = 0
    grand_errors = 0

    for ep in endpoints:
        items, errs = scrape_endpoint(auth, conn, ep)
        grand_total += items
        grand_errors += errs
        time.sleep(REQUEST_DELAY)

    print(f"\n{'='*60}")
    print(f"  LAYER 2 EXTRACTION COMPLETE")
    print(f"  Total items: {grand_total}")
    print(f"  Total errors: {grand_errors}")
    print(f"{'='*60}")

    # Summary
    print("\n  App Tables:")
    for ep in endpoints:
        table_name = f"app_{ep['name']}"
        try:
            count = conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]
            print(f"    {table_name}: {count} rows")
        except Exception:
            print(f"    {table_name}: (table not found)")

    conn.close()


if __name__ == "__main__":
    run_one_shot()
