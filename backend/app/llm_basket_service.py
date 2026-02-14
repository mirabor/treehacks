"""LLM-generated basket: fetch open markets, ask OpenAI to pick markets + directions + weights."""
from __future__ import annotations

import json
from typing import Any, Optional

from app.kalshi_client import KalshiClient
from app.models import BasketLeg, BasketTheme, Direction

OPENAI_BASKET_SCHEMA = {
    "name": "basket",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "theme_name": {"type": "string", "description": "Short name for the basket"},
            "description": {"type": "string", "description": "One sentence description"},
            "legs": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "market_ticker": {"type": "string", "description": "Must be one of the provided tickers"},
                        "direction": {
                            "type": "string",
                            "enum": ["BUY_YES", "BUY_NO", "SELL_YES", "SELL_NO"],
                        },
                        "weight": {"type": "number", "description": "Fraction 0-1, will be renormalized"},
                        "rationale": {"type": "string", "description": "Brief reason for this leg"},
                    },
                    "required": ["market_ticker", "direction", "weight", "rationale"],
                    "additionalProperties": False,
                },
                "minItems": 1,
                "maxItems": 10,
            },
        },
        "required": ["theme_name", "description", "legs"],
        "additionalProperties": False,
    },
}

CANDIDATE_MAX = 80
LEG_MAX = 10


def _market_doc(m: dict) -> str:
    ticker = m.get("ticker", "")
    title = (m.get("title") or m.get("subtitle") or "").strip() or "(no title)"
    yes_sub = (m.get("yes_sub_title") or "").strip()
    no_sub = (m.get("no_sub_title") or "").strip()
    event = (m.get("event_ticker") or "").strip()
    rules = (m.get("rules_primary") or "").strip()[:200]
    return f"{ticker} | {title} | yes: {yes_sub} / no: {no_sub} | event: {event} | {rules}"


def generate_basket(query: str, kalshi: KalshiClient, openai_api_key: str) -> BasketTheme:
    """Fetch open markets, ask LLM to pick 5–10 with directions and weights, return BasketTheme."""
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY not set")

    markets = kalshi.get_open_markets(limit=500)
    if not markets:
        raise ValueError("No open markets returned from Kalshi")

    # Build candidate list (use first CANDIDATE_MAX to stay under context)
    candidates = [{"ticker": m["ticker"], "doc": _market_doc(m), "market": m} for m in markets[:CANDIDATE_MAX]]
    ticker_set = {c["ticker"] for c in candidates}
    candidates_text = "\n".join(c["doc"] for c in candidates)

    from openai import OpenAI

    client = OpenAI(api_key=openai_api_key)
    prompt = f"""You are building a prediction-market "basket" (like an ETF) on Kalshi.

The user's trend or belief: "{query}"

Below are CANDIDATE MARKETS (one per line). Each line is: ticker | title | yes: ... / no: ... | event: ... | rules...

CANDIDATE MARKETS:
{candidates_text}

Choose 5 to 10 markets that best fit the user's trend. For each leg set:
- market_ticker: must be EXACTLY one of the tickers from the list above (copy-paste it).
- direction: BUY_YES, BUY_NO, SELL_YES, or SELL_NO (e.g. if user thinks something won't happen, use SELL_YES or BUY_NO).
- weight: a number between 0 and 1 (they will be renormalized to sum to 1).
- rationale: one short sentence.

Return valid JSON only."""

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_schema", "json_schema": OPENAI_BASKET_SCHEMA},
    )
    raw = resp.choices[0].message.content
    data = json.loads(raw)

    legs_raw = data.get("legs", [])
    market_by_ticker = {m["ticker"]: m for m in markets}

    # Filter: only allow tickers from candidate list; cap at LEG_MAX
    out_legs = []
    for leg in legs_raw[:LEG_MAX]:
        ticker = (leg.get("market_ticker") or "").strip()
        if ticker not in ticker_set:
            continue
        direction = leg.get("direction", "BUY_YES")
        if direction not in ("BUY_YES", "BUY_NO", "SELL_YES", "SELL_NO"):
            direction = "BUY_YES"
        weight = float(leg.get("weight", 0.2))
        weight = max(0.0, min(1.0, weight))
        m = market_by_ticker.get(ticker, {})
        event_ticker = m.get("event_ticker", ticker)
        title = m.get("title") or m.get("subtitle") or ticker
        out_legs.append(
            BasketLeg(
                market_ticker=ticker,
                event_ticker=event_ticker,
                title=title,
                direction=direction,
                weight=weight,
                enabled=True,
            )
        )

    if not out_legs:
        raise ValueError("LLM returned no valid legs (tickers must be from the candidate list)")

    # Renormalize weights
    total_w = sum(l.weight for l in out_legs)
    if total_w <= 0:
        total_w = 1.0
    for l in out_legs:
        l.weight /= total_w

    return BasketTheme(
        theme_id="generated",
        name=(data.get("theme_name") or "Generated basket").strip()[:100],
        description=(data.get("description") or "").strip()[:500],
        legs=out_legs,
    )
