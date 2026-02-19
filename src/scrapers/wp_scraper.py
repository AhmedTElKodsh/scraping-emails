"""One-shot WordPress REST API scraper for farida.estate public content."""

import requests
import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.storage.database import (
    get_connection, init_db,
    upsert_wp_post, upsert_wp_page, upsert_wp_media,
    upsert_wp_category, upsert_wp_tag, upsert_wp_user,
    log_scrape_start, log_scrape_end,
)

BASE_URL = "https://farida.estate/wp-json/wp/v2"
REQUEST_DELAY = 2  # seconds between requests
PER_PAGE = 100

# Map endpoint names to their upsert functions
ENDPOINTS = {
    "posts": upsert_wp_post,
    "pages": upsert_wp_page,
    "media": upsert_wp_media,
    "categories": upsert_wp_category,
    "tags": upsert_wp_tag,
    "users": upsert_wp_user,
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/json",
}


def fetch_endpoint(endpoint_name, upsert_fn, conn):
    """Fetch all items from a WP REST API endpoint with pagination."""
    url = f"{BASE_URL}/{endpoint_name}"
    page = 1
    total_items = 0
    errors = 0

    run_id = log_scrape_start(conn, "wp", endpoint_name)
    print(f"\n{'='*60}")
    print(f"  Scraping: {endpoint_name}")
    print(f"{'='*60}")

    try:
        while True:
            params = {"page": page, "per_page": PER_PAGE}
            print(f"  Page {page}...", end=" ", flush=True)

            try:
                resp = requests.get(url, params=params, headers=HEADERS, timeout=30)
            except requests.RequestException as e:
                print(f"REQUEST ERROR: {e}")
                errors += 1
                break

            if resp.status_code == 400:
                # WP returns 400 when page exceeds total pages
                print("No more pages.")
                break

            if resp.status_code != 200:
                print(f"HTTP {resp.status_code}")
                errors += 1
                break

            try:
                items = resp.json()
            except ValueError:
                print("Invalid JSON response")
                errors += 1
                break

            if not items:
                print("Empty response.")
                break

            for item in items:
                try:
                    upsert_fn(conn, item)
                    total_items += 1
                except Exception as e:
                    print(f"\n    Error upserting item {item.get('id', '?')}: {e}")
                    errors += 1

            conn.commit()

            total_pages = int(resp.headers.get("X-WP-TotalPages", 1))
            total_available = resp.headers.get("X-WP-Total", "?")
            print(f"{len(items)} items (page {page}/{total_pages}, total available: {total_available})")

            if page >= total_pages:
                break

            page += 1
            time.sleep(REQUEST_DELAY)

        log_scrape_end(conn, run_id, total_items, errors)
        print(f"  Result: {total_items} items scraped, {errors} errors")

    except Exception as e:
        log_scrape_end(conn, run_id, total_items, errors, "failed", str(e))
        print(f"  FAILED: {e}")
        raise

    return total_items, errors


def check_api_available():
    """Verify the WordPress REST API is accessible."""
    print("Checking WordPress REST API availability...")
    try:
        resp = requests.get(
            "https://farida.estate/wp-json/",
            headers=HEADERS,
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            site_name = data.get("name", "Unknown")
            site_desc = data.get("description", "")
            print(f"  Site: {site_name}")
            print(f"  Description: {site_desc}")
            print(f"  API URL: {data.get('url', 'N/A')}")
            print(f"  Namespaces: {', '.join(data.get('namespaces', []))}")
            return True
        else:
            print(f"  API returned HTTP {resp.status_code}")
            return False
    except requests.RequestException as e:
        print(f"  API not reachable: {e}")
        return False


def run_one_shot():
    """Execute one-shot extraction of all WordPress content."""
    print("\n" + "=" * 60)
    print("  FARIDA.ESTATE — WordPress One-Shot Extraction")
    print("=" * 60)

    if not check_api_available():
        print("\nWordPress REST API is not available. Aborting.")
        return

    conn = get_connection()
    init_db(conn)

    grand_total = 0
    grand_errors = 0

    for endpoint_name, upsert_fn in ENDPOINTS.items():
        items, errs = fetch_endpoint(endpoint_name, upsert_fn, conn)
        grand_total += items
        grand_errors += errs
        time.sleep(REQUEST_DELAY)

    print(f"\n{'='*60}")
    print(f"  EXTRACTION COMPLETE")
    print(f"  Total items: {grand_total}")
    print(f"  Total errors: {grand_errors}")
    print(f"  Database: data/farida.db")
    print(f"{'='*60}")

    # Print summary per table
    print("\n  Table Summary:")
    for table in ["wp_posts", "wp_pages", "wp_media", "wp_categories", "wp_tags", "wp_users"]:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"    {table}: {count} rows")

    scrape_runs = conn.execute(
        "SELECT endpoint, items_scraped, status FROM scrape_runs ORDER BY id DESC LIMIT 10"
    ).fetchall()
    print("\n  Scrape Run Log:")
    for row in scrape_runs:
        print(f"    {row['endpoint']}: {row['items_scraped']} items [{row['status']}]")

    conn.close()


if __name__ == "__main__":
    run_one_shot()
