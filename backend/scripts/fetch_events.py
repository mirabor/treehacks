#!/usr/bin/env python3
"""Fetch all open events from Kalshi demo and save to events_list.json. Run from backend/."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add parent to path for app imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.kalshi_client import KalshiClient


def main():
    client = KalshiClient()
    print("Fetching open events (with nested markets)...")
    events = client.get_open_events(with_nested_markets=True)

    total_markets = sum(len(e.get("markets", [])) for e in events)
    fetched_at = datetime.now(timezone.utc).isoformat()

    # Full export (large; add to .gitignore if needed)
    out_full = {
        "fetched_at": fetched_at,
        "count": len(events),
        "total_markets": total_markets,
        "events": events,
    }
    out_full_path = Path(__file__).resolve().parent.parent / "events_list.json"
    with open(out_full_path, "w") as f:
        json.dump(out_full, f, indent=2)
    print(f"Saved full list to {out_full_path} ({len(events)} events, {total_markets} markets)")

    # Slim summary for repo reference (event_ticker, title, series, market_count, tickers)
    summary = {
        "fetched_at": fetched_at,
        "count": len(events),
        "total_markets": total_markets,
        "events": [
            {
                "event_ticker": e.get("event_ticker"),
                "title": (e.get("title") or "")[:120],
                "series_ticker": e.get("series_ticker"),
                "market_count": len(e.get("markets", [])),
                "market_tickers": [m.get("ticker") for m in e.get("markets", []) if m.get("ticker")],
            }
            for e in events
        ],
    }
    summary_path = Path(__file__).resolve().parent.parent / "events_list_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Saved summary to {summary_path} (for repo reference)")

    # Print summary
    for i, e in enumerate(events[:20]):
        title = (e.get("title") or e.get("event_ticker", ""))[:60]
        mcount = len(e.get("markets", []))
        series = e.get("series_ticker", "")
        print(f"  {i+1}. {title}... ({mcount} markets) [{series}]")
    if len(events) > 20:
        print(f"  ... and {len(events) - 20} more")


if __name__ == "__main__":
    main()
