#!/usr/bin/env python3
"""Collect daily headlines from the Guardian Content API and Telegraph RSS feeds
into a local SQLite database (headlines.db).

Set the Guardian API key in the environment before running:

    export GUARDIAN_API_KEY=your-key-here
    python collect_headlines.py
"""

import os
import sqlite3
import sys
from datetime import datetime, timezone

import feedparser
import requests

DB_PATH = "headlines.db"

GUARDIAN_API_URL = "https://content.guardianapis.com/search"
GUARDIAN_SECTIONS = ["uk-news", "politics", "business", "money"]

TELEGRAPH_FEEDS = {
    "news": "https://www.telegraph.co.uk/news/rss.xml",
    "politics": "https://www.telegraph.co.uk/politics/rss.xml",
    "business": "https://www.telegraph.co.uk/business/rss.xml",
    "money": "https://www.telegraph.co.uk/money/rss.xml",
}


def init_db(conn):
    """Create the headlines table if it does not already exist."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS headlines (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            outlet       TEXT NOT NULL,
            section      TEXT NOT NULL,
            headline     TEXT NOT NULL,
            url          TEXT NOT NULL UNIQUE,
            published_at TEXT,
            collected_at TEXT NOT NULL
        )
        """
    )
    conn.commit()


def store(conn, rows):
    """Insert rows, ignoring any whose url already exists.

    Returns the number of newly inserted rows.
    """
    before = conn.total_changes
    conn.executemany(
        """
        INSERT OR IGNORE INTO headlines
            (outlet, section, headline, url, published_at, collected_at)
        VALUES (:outlet, :section, :headline, :url, :published_at, :collected_at)
        """,
        rows,
    )
    conn.commit()
    return conn.total_changes - before


def collect_guardian(api_key, collected_at):
    """Fetch headlines from the Guardian Content API for each section."""
    rows = []
    for section in GUARDIAN_SECTIONS:
        params = {
            "api-key": api_key,
            "section": section,
            "order-by": "newest",
            "page-size": 50,
        }
        try:
            resp = requests.get(GUARDIAN_API_URL, params=params, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as exc:
            print(f"  ! Guardian '{section}' request failed: {exc}", file=sys.stderr)
            continue

        results = resp.json().get("response", {}).get("results", [])
        for item in results:
            rows.append(
                {
                    "outlet": "Guardian",
                    "section": section,
                    "headline": item.get("webTitle", ""),
                    "url": item.get("webUrl", ""),
                    "published_at": item.get("webPublicationDate"),
                    "collected_at": collected_at,
                }
            )
        print(f"  Guardian/{section}: {len(results)} fetched")
    return rows


def collect_telegraph(collected_at):
    """Fetch headlines from the Telegraph RSS feeds."""
    rows = []
    for section, url in TELEGRAPH_FEEDS.items():
        feed = feedparser.parse(url)
        if feed.bozo:
            print(
                f"  ! Telegraph '{section}' feed parse warning: {feed.bozo_exception}",
                file=sys.stderr,
            )
        for entry in feed.entries:
            rows.append(
                {
                    "outlet": "Telegraph",
                    "section": section,
                    "headline": entry.get("title", ""),
                    "url": entry.get("link", ""),
                    "published_at": entry.get("published"),
                    "collected_at": collected_at,
                }
            )
        print(f"  Telegraph/{section}: {len(feed.entries)} fetched")
    return rows


def main():
    api_key = os.environ.get("GUARDIAN_API_KEY")
    if not api_key:
        print(
            "Error: GUARDIAN_API_KEY environment variable is not set.",
            file=sys.stderr,
        )
        return 1

    collected_at = datetime.now(timezone.utc).isoformat()

    conn = sqlite3.connect(DB_PATH)
    try:
        init_db(conn)

        # Drop rows with an empty url so the UNIQUE constraint stays meaningful.
        print("Collecting Guardian headlines...")
        guardian_rows = [r for r in collect_guardian(api_key, collected_at) if r["url"]]

        print("Collecting Telegraph headlines...")
        telegraph_rows = [r for r in collect_telegraph(collected_at) if r["url"]]

        all_rows = guardian_rows + telegraph_rows
        inserted = store(conn, all_rows)

        total = conn.execute("SELECT COUNT(*) FROM headlines").fetchone()[0]
        print(
            f"\nFetched {len(all_rows)} headlines, "
            f"inserted {inserted} new (duplicates ignored)."
        )
        print(f"Database now holds {total} headlines in {DB_PATH}.")
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
