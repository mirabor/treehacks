#!/usr/bin/env python3
"""Update themes.json with valid open markets from Kalshi demo. Run from backend/."""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Add parent to path for app imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.kalshi_client import KalshiClient


def main():
    client = KalshiClient()
    markets = client.get_open_markets(limit=500)

    # Group by event/prefix for theme building
    quicksettle = [m for m in markets if (m.get("ticker") or "").startswith("KXQUICKSETTLE-")]
    tester = [m for m in markets if (m.get("ticker") or "").startswith("KXTESTER-")]
    denver = [m for m in markets if (m.get("ticker") or "").startswith("KXHIGHDEN-")]
    la = [m for m in markets if (m.get("ticker") or "").startswith("KXHIGHLAX-")]

    themes = []

    # Math & Logic: quicksettle -2 (1+1=2) and -3 (1+1=3), plus tester
    qs_2 = next((m for m in quicksettle if m.get("ticker", "").endswith("-2")), None)
    qs_3 = next((m for m in quicksettle if m.get("ticker", "").endswith("-3")), None)
    tm1 = next((m for m in tester if "M1" in (m.get("ticker") or "")), tester[0] if tester else None)

    math_legs = []
    if qs_2:
        math_legs.append(_leg(qs_2, "BUY_YES", 0.34, "Will 1+1 equal 2?"))
    if qs_3:
        math_legs.append(_leg(qs_3, "BUY_NO", 0.33, "Will 1+1 equal 3?"))
    if tm1:
        math_legs.append(_leg(tm1, "BUY_YES", 0.33, tm1.get("title") or "Test Market 1"))

    if math_legs:
        themes.append({
            "theme_id": "math_and_logic",
            "name": "Math & Logic",
            "description": "Simple yes/no markets and test market.",
            "legs": math_legs,
        })

    # Denver Weather: top 3 buckets by ticker
    denver_sorted = sorted(denver, key=lambda m: m.get("ticker", ""))[:3]
    if denver_sorted:
        themes.append({
            "theme_id": "denver_weather",
            "name": "Denver Weather",
            "description": "High temperature in Denver on Feb 15, 2026.",
            "legs": [_leg(m, "BUY_YES", 1.0 / len(denver_sorted), m.get("title") or m.get("ticker", "")) for m in denver_sorted],
        })

    # LA Weather
    la_sorted = sorted(la, key=lambda m: m.get("ticker", ""))[:3]
    if la_sorted:
        themes.append({
            "theme_id": "la_weather",
            "name": "LA Weather",
            "description": "High temperature in LA on Feb 15, 2026.",
            "legs": [_leg(m, "BUY_YES", 1.0 / len(la_sorted), m.get("title") or m.get("ticker", "")) for m in la_sorted],
        })

    out_path = Path(__file__).resolve().parent.parent / "themes.json"
    with open(out_path, "w") as f:
        json.dump(themes, f, indent=2)

    print(f"Updated {out_path} with {len(themes)} themes, {sum(len(t['legs']) for t in themes)} legs.")
    for t in themes:
        tickers = [l["market_ticker"] for l in t["legs"]]
        print(f"  - {t['name']}: {tickers}")


def _leg(m: dict, direction: str, weight: float, title: str) -> dict:
    return {
        "market_ticker": m.get("ticker", ""),
        "event_ticker": m.get("event_ticker", ""),
        "title": title,
        "direction": direction,
        "weight": weight,
        "enabled": True,
    }


if __name__ == "__main__":
    main()
