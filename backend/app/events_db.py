"""SQLite database for searchable events. Populate with scripts/init_events_db.py."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Optional

DB_PATH = Path(__file__).resolve().parent.parent / "events.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            event_ticker TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            series_ticker TEXT,
            category TEXT,
            market_count INTEGER DEFAULT 0,
            volume INTEGER DEFAULT 0,
            markets_json TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_volume ON events(volume DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_title ON events(title)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_series ON events(series_ticker)")
    conn.commit()


def upsert_event(
    conn: sqlite3.Connection,
    event_ticker: str,
    title: str,
    series_ticker: str,
    category: str,
    market_count: int,
    volume: int,
    markets_json: str,
) -> None:
    conn.execute(
        """
        INSERT INTO events (event_ticker, title, series_ticker, category, market_count, volume, markets_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(event_ticker) DO UPDATE SET
            title = excluded.title,
            series_ticker = excluded.series_ticker,
            category = excluded.category,
            market_count = excluded.market_count,
            volume = excluded.volume,
            markets_json = excluded.markets_json
        """,
        (event_ticker, title, series_ticker, category, market_count, volume, markets_json),
    )


def search_events(q: Optional[str] = None, limit: int = 20) -> list[dict[str, Any]]:
    """Search events by keyword. Returns top `limit` by volume (matching q if provided)."""
    conn = get_conn()
    try:
        if q and q.strip():
            pattern = f"%{q.strip()}%"
            rows = conn.execute(
                """
                SELECT event_ticker, title, series_ticker, category, market_count, volume, markets_json
                FROM events
                WHERE title LIKE ? OR series_ticker LIKE ? OR event_ticker LIKE ? OR category LIKE ?
                ORDER BY volume DESC
                LIMIT ?
                """,
                (pattern, pattern, pattern, pattern, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT event_ticker, title, series_ticker, category, market_count, volume, markets_json
                FROM events
                ORDER BY volume DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        out = []
        for r in rows:
            markets = []
            if r["markets_json"]:
                try:
                    markets = json.loads(r["markets_json"])
                except json.JSONDecodeError:
                    pass
            out.append({
                "event_ticker": r["event_ticker"],
                "title": r["title"],
                "series_ticker": r["series_ticker"] or "",
                "category": r["category"] or "",
                "market_count": r["market_count"] or 0,
                "volume": r["volume"] or 0,
                "markets": markets,
            })
        return out
    finally:
        conn.close()


def get_event(event_ticker: str) -> Optional[dict[str, Any]]:
    """Get one event by ticker."""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT event_ticker, title, series_ticker, category, market_count, volume, markets_json FROM events WHERE event_ticker = ?",
            (event_ticker,),
        ).fetchone()
        if not row:
            return None
        markets = []
        if row["markets_json"]:
            try:
                markets = json.loads(row["markets_json"])
            except json.JSONDecodeError:
                pass
        return {
            "event_ticker": row["event_ticker"],
            "title": row["title"],
            "series_ticker": row["series_ticker"] or "",
            "category": row["category"] or "",
            "market_count": row["market_count"] or 0,
            "volume": row["volume"] or 0,
            "markets": markets,
        }
    finally:
        conn.close()
