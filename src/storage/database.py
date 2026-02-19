"""SQLite storage for scraped data from farida.estate."""

import sqlite3
import json
import os
from datetime import datetime, timezone


DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "farida.db")


def get_connection(db_path=None):
    path = db_path or DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn):
    """Create all tables if they don't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS wp_posts (
            id INTEGER PRIMARY KEY,
            title TEXT,
            slug TEXT,
            content TEXT,
            excerpt TEXT,
            date_published TEXT,
            date_modified TEXT,
            author_id INTEGER,
            status TEXT,
            url TEXT,
            categories TEXT,  -- JSON array of category IDs
            tags TEXT,        -- JSON array of tag IDs
            featured_media INTEGER,
            raw_json TEXT,
            scraped_at TEXT
        );

        CREATE TABLE IF NOT EXISTS wp_pages (
            id INTEGER PRIMARY KEY,
            title TEXT,
            slug TEXT,
            content TEXT,
            date_published TEXT,
            date_modified TEXT,
            status TEXT,
            url TEXT,
            raw_json TEXT,
            scraped_at TEXT
        );

        CREATE TABLE IF NOT EXISTS wp_media (
            id INTEGER PRIMARY KEY,
            title TEXT,
            slug TEXT,
            source_url TEXT,
            mime_type TEXT,
            alt_text TEXT,
            date_published TEXT,
            raw_json TEXT,
            scraped_at TEXT
        );

        CREATE TABLE IF NOT EXISTS wp_categories (
            id INTEGER PRIMARY KEY,
            name TEXT,
            slug TEXT,
            description TEXT,
            parent INTEGER,
            count INTEGER,
            raw_json TEXT,
            scraped_at TEXT
        );

        CREATE TABLE IF NOT EXISTS wp_tags (
            id INTEGER PRIMARY KEY,
            name TEXT,
            slug TEXT,
            description TEXT,
            count INTEGER,
            raw_json TEXT,
            scraped_at TEXT
        );

        CREATE TABLE IF NOT EXISTS wp_users (
            id INTEGER PRIMARY KEY,
            name TEXT,
            slug TEXT,
            description TEXT,
            url TEXT,
            avatar_urls TEXT,  -- JSON
            raw_json TEXT,
            scraped_at TEXT
        );

        CREATE TABLE IF NOT EXISTS scrape_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            layer TEXT NOT NULL,       -- 'wp' or 'app'
            endpoint TEXT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            items_scraped INTEGER DEFAULT 0,
            errors INTEGER DEFAULT 0,
            status TEXT DEFAULT 'running',  -- running, completed, failed
            error_message TEXT
        );
    """)
    conn.commit()


def upsert_wp_post(conn, item):
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("""
        INSERT INTO wp_posts (id, title, slug, content, excerpt, date_published,
            date_modified, author_id, status, url, categories, tags,
            featured_media, raw_json, scraped_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            title=excluded.title, slug=excluded.slug, content=excluded.content,
            excerpt=excluded.excerpt, date_modified=excluded.date_modified,
            status=excluded.status, url=excluded.url, categories=excluded.categories,
            tags=excluded.tags, raw_json=excluded.raw_json, scraped_at=excluded.scraped_at
    """, (
        item["id"],
        item.get("title", {}).get("rendered", ""),
        item.get("slug", ""),
        item.get("content", {}).get("rendered", ""),
        item.get("excerpt", {}).get("rendered", ""),
        item.get("date", ""),
        item.get("modified", ""),
        item.get("author", 0),
        item.get("status", ""),
        item.get("link", ""),
        json.dumps(item.get("categories", [])),
        json.dumps(item.get("tags", [])),
        item.get("featured_media", 0),
        json.dumps(item),
        now,
    ))


def upsert_wp_page(conn, item):
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("""
        INSERT INTO wp_pages (id, title, slug, content, date_published,
            date_modified, status, url, raw_json, scraped_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            title=excluded.title, slug=excluded.slug, content=excluded.content,
            date_modified=excluded.date_modified, status=excluded.status,
            url=excluded.url, raw_json=excluded.raw_json, scraped_at=excluded.scraped_at
    """, (
        item["id"],
        item.get("title", {}).get("rendered", ""),
        item.get("slug", ""),
        item.get("content", {}).get("rendered", ""),
        item.get("date", ""),
        item.get("modified", ""),
        item.get("status", ""),
        item.get("link", ""),
        json.dumps(item),
        now,
    ))


def upsert_wp_media(conn, item):
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("""
        INSERT INTO wp_media (id, title, slug, source_url, mime_type, alt_text,
            date_published, raw_json, scraped_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            title=excluded.title, source_url=excluded.source_url,
            mime_type=excluded.mime_type, alt_text=excluded.alt_text,
            raw_json=excluded.raw_json, scraped_at=excluded.scraped_at
    """, (
        item["id"],
        item.get("title", {}).get("rendered", ""),
        item.get("slug", ""),
        item.get("source_url", ""),
        item.get("mime_type", ""),
        item.get("alt_text", ""),
        item.get("date", ""),
        json.dumps(item),
        now,
    ))


def upsert_wp_category(conn, item):
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("""
        INSERT INTO wp_categories (id, name, slug, description, parent, count, raw_json, scraped_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name, slug=excluded.slug, description=excluded.description,
            count=excluded.count, raw_json=excluded.raw_json, scraped_at=excluded.scraped_at
    """, (
        item["id"], item.get("name", ""), item.get("slug", ""),
        item.get("description", ""), item.get("parent", 0),
        item.get("count", 0), json.dumps(item), now,
    ))


def upsert_wp_tag(conn, item):
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("""
        INSERT INTO wp_tags (id, name, slug, description, count, raw_json, scraped_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name, slug=excluded.slug, description=excluded.description,
            count=excluded.count, raw_json=excluded.raw_json, scraped_at=excluded.scraped_at
    """, (
        item["id"], item.get("name", ""), item.get("slug", ""),
        item.get("description", ""), item.get("count", 0),
        json.dumps(item), now,
    ))


def upsert_wp_user(conn, item):
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("""
        INSERT INTO wp_users (id, name, slug, description, url, avatar_urls, raw_json, scraped_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name, slug=excluded.slug, description=excluded.description,
            url=excluded.url, avatar_urls=excluded.avatar_urls,
            raw_json=excluded.raw_json, scraped_at=excluded.scraped_at
    """, (
        item["id"], item.get("name", ""), item.get("slug", ""),
        item.get("description", ""), item.get("url", ""),
        json.dumps(item.get("avatar_urls", {})), json.dumps(item), now,
    ))


def log_scrape_start(conn, layer, endpoint):
    now = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        "INSERT INTO scrape_runs (layer, endpoint, started_at) VALUES (?, ?, ?)",
        (layer, endpoint, now)
    )
    conn.commit()
    return cur.lastrowid


def log_scrape_end(conn, run_id, items_scraped, errors=0, status="completed", error_message=None):
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("""
        UPDATE scrape_runs SET finished_at=?, items_scraped=?, errors=?,
            status=?, error_message=? WHERE id=?
    """, (now, items_scraped, errors, status, error_message, run_id))
    conn.commit()
