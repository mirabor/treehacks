#!/usr/bin/env python3
"""Build themes.json from interesting events in the DB. Run from backend/."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.events_db import get_event

# Event tickers for diverse, interesting themes (by volume / appeal)
EVENT_TICKERS = [
    "KXLEADERSOUT-27JAN01",      # World leaders out before 2027?
    "KXKHAMENEIOUT-AKHA",       # Ali Khamenei out as Supreme Leader?
    "KXNHL-26",                 # Pro Hockey Champion?
    "KXPRESPERSON-28",          # Who will win the next presidential election?
    "KXMJSCHEDULE",             # Will Marijuana be Rescheduled?
    "KXOSCARPIC-26",            # Oscar for Best Picture?
    "KXVENEZUELALEADER-26DEC31",# Who will lead Venezuela at the end of 2026?
    "KXMENWORLDCUP-26",         # 2026 Men's World Cup winner?
    "KXNBAMVP-26",              # Pro Basketball MVP Winner?
    "KXPREMIERLEAGUE-26",       # English Premier League Winner?
    "KXPGATOUR-ATPBP26",        # AT&T Pebble Beach Pro-Am Winner?
    "KXFEDCHAIRNOM-29",         # Who will Trump nominate as Fed Chair?
]


def slug(s: str) -> str:
    return s.lower().replace("-", "_")


def main():
    themes = []
    for event_ticker in EVENT_TICKERS:
        ev = get_event(event_ticker)
        if not ev:
            print(f"Skip {event_ticker}: not found")
            continue
        markets = ev.get("markets", [])
        if not markets:
            print(f"Skip {event_ticker}: no markets")
            continue
        n = len(markets)
        legs = [
            {
                "market_ticker": m.get("market_ticker", ""),
                "event_ticker": m.get("event_ticker", ev.get("event_ticker", "")),
                "title": m.get("title", m.get("market_ticker", "Market")),
                "direction": "BUY_YES",
                "weight": 1.0 / n,
                "enabled": True,
            }
            for m in markets if m.get("market_ticker")
        ]
        themes.append({
            "theme_id": slug(event_ticker),
            "name": ev.get("title", event_ticker),
            "description": f"Event: {ev.get('title', '')}",
            "legs": legs,
        })
        print(f"  {ev.get('title', '')[:50]}: {len(legs)} markets")

    out_path = Path(__file__).resolve().parent.parent / "themes.json"
    with open(out_path, "w") as f:
        json.dump(themes, f, indent=2)

    print(f"\nWrote {out_path} with {len(themes)} themes")


if __name__ == "__main__":
    main()
