"""Test helpers: place single order, search market by LLM query."""
from __future__ import annotations

import uuid
from typing import Any, Optional

from app.config import OPENAI_API_KEY
from app.kalshi_client import KalshiClient

# Known open market on Kalshi demo (Denver high temp 70-71°)
HARDCODED_TICKER = "KXHIGHDEN-26FEB15-B70.5"
HARDCODED_TITLE = "Denver high temp 70–71° on Feb 15, 2026"


def place_order(kalshi: KalshiClient, ticker: str, side: str = "yes", count: int = 1) -> dict[str, Any]:
    """
    Place 1 contract buy at the ask (IOC). Returns Kalshi batch response or error dict.
    side: "yes" or "no"
    """
    markets = kalshi.get_markets([ticker])
    m = markets.get(ticker)
    if not m:
        return {"success": False, "error": "Market not found", "ticker": ticker}

    if side == "yes":
        price_raw = m.get("yes_ask_dollars")
    else:
        price_raw = m.get("no_ask_dollars")

    try:
        price = float(str(price_raw or "0").strip())
    except (ValueError, TypeError):
        price = 0.0

    if price <= 0 or price >= 1.0:
        price = 0.50

    price_str = f"{max(0.01, min(0.99, price)):.4f}"
    order = {
        "ticker": ticker,
        "side": side,
        "action": "buy",
        "count": count,
        "client_order_id": f"test:{uuid.uuid4().hex[:8]}",
        "time_in_force": "good_till_canceled",
    }
    if side == "yes":
        order["yes_price_dollars"] = price_str
    else:
        order["no_price_dollars"] = price_str

    try:
        resp = kalshi.batch_create_orders([order])
    except Exception as e:
        return {"success": False, "error": str(e), "ticker": ticker}

    items = resp.get("orders", [])
    if not items:
        return {"success": False, "error": "Empty batch response", "ticker": ticker}

    item = items[0]
    err = item.get("error")
    o = item.get("order")
    if err:
        msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
        return {
            "success": False,
            "error": msg,
            "ticker": ticker,
            "order_id": None,
            "status": None,
        }
    return {
        "success": True,
        "ticker": ticker,
        "order_id": o.get("order_id") if o else None,
        "status": o.get("status") if o else None,
        "fill_count": o.get("fill_count", 0) if o else 0,
        "remaining_count": o.get("remaining_count", 0) if o else 0,
    }


def search_market_by_query(kalshi: KalshiClient, query: str, openai_key: str) -> dict[str, Any]:
    """
    Use LLM to pick the single best-matching open market for the query.
    Returns { ticker, title } or { error }.
    """
    if not openai_key:
        return {"error": "OPENAI_API_KEY not set"}

    markets = kalshi.get_open_markets(limit=100)
    if not markets:
        return {"error": "No open markets"}

    candidates = [
        {
            "ticker": m["ticker"],
            "title": (m.get("title") or m.get("subtitle") or m.get("yes_sub_title") or "").strip()[:150],
        }
        for m in markets[:60]
    ]
    candidates_text = "\n".join(f"- {c['ticker']}: {c['title']}" for c in candidates)

    from openai import OpenAI

    client = OpenAI(api_key=openai_key)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": f'''Given the user query: "{query}"

Here are open Kalshi markets (one per line: ticker: title):
{candidates_text}

Pick the SINGLE best matching market. Respond with ONLY the ticker, nothing else. If no good match, respond with the first ticker in the list.''',
            }
        ],
        max_tokens=50,
    )
    raw = (resp.choices[0].message.content or "").strip()
    ticker_set = {c["ticker"] for c in candidates}
    ticker = None
    for t in ticker_set:
        if t in raw or raw.endswith(t):
            ticker = t
            break
    if not ticker:
        for word in raw.replace(",", " ").split():
            w = "".join(c for c in word if c.isalnum() or c in "-_.")
            if w in ticker_set:
                ticker = w
                break
    if not ticker:
        ticker = candidates[0]["ticker"]

    title = next((c["title"] for c in candidates if c["ticker"] == ticker), ticker)
    return {"ticker": ticker, "title": title}
