#!/usr/bin/env python3
"""Initialize events SQLite database from Kalshi API. Run from backend/."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.events_db import init_schema, upsert_event, get_conn
from app.kalshi_client import KalshiClient


def _parse_volume(m: dict) -> int:
    v = m.get("volume")
    if v is not None:
        try:
            return int(v)
        except (ValueError, TypeError):
            pass
    vfp = m.get("volume_fp")
    if vfp is not None:
        try:
            return int(float(str(vfp).strip()))
        except (ValueError, TypeError):
            pass
    return 0


def main():
    client = KalshiClient()
    print("Fetching open events (with nested markets)...")
    events = client.get_open_events(with_nested_markets=True)

    conn = get_conn()
    init_schema(conn)

    for e in events:
        event_ticker = e.get("event_ticker", "")
        title = e.get("title", "")
        series_ticker = e.get("series_ticker", "") or ""
        category = e.get("category", "") or ""
        markets_raw = e.get("markets", [])
        market_count = len(markets_raw)
        volume = sum(_parse_volume(m) for m in markets_raw)
        markets_json = json.dumps([
            {
                "market_ticker": m.get("ticker", ""),
                "event_ticker": m.get("event_ticker", event_ticker),
                "title": (m.get("yes_sub_title") or m.get("title") or m.get("ticker", ""))[:200],
            }
            for m in markets_raw if m.get("ticker")
        ])
        upsert_event(conn, event_ticker, title, series_ticker, category, market_count, volume, markets_json)

    conn.commit()
    conn.close()

    print(f"Inserted {len(events)} events into events.db")
    print("Run the app and use search to browse.")


if __name__ == "__main__":
    main()
