"""FastAPI app: themes and basket preview/execute."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException

from app.basket_service import execute, preview
from app.events_db import get_event, search_events
from app.config import OPENAI_API_KEY
from app.kalshi_client import KalshiClient
from app.llm_basket_service import generate_basket
from app.test_order import HARDCODED_TICKER, HARDCODED_TITLE, place_order, search_market_by_query
from app.models import (
    BasketTheme,
    ExecuteRequest,
    ExecuteResponse,
    BatchOrderResultLeg,
    GenerateRequest,
    PreviewRequest,
)

app = FastAPI(title="Kalshi ETF Baskets", version="0.1.0")

THEMES_PATH = Path(__file__).resolve().parent.parent / "themes.json"
_themes: Optional[list[BasketTheme]] = None
_kalshi: Optional[KalshiClient] = None


def get_themes() -> list[BasketTheme]:
    global _themes
    if _themes is None:
        with open(THEMES_PATH) as f:
            raw = json.load(f)
        _themes = [BasketTheme(**t) for t in raw]
    return _themes


def get_kalshi() -> KalshiClient:
    global _kalshi
    if _kalshi is None:
        _kalshi = KalshiClient()
    return _kalshi


@app.get("/themes")
def list_themes():
    """List all basket themes."""
    return {"themes": [t.model_dump() for t in get_themes()]}


@app.get("/themes/{theme_id}")
def get_theme(theme_id: str):
    """Get one theme by id."""
    for t in get_themes():
        if t.theme_id == theme_id:
            return t.model_dump()
    raise HTTPException(status_code=404, detail="Theme not found")


def _resolve_theme(body: PreviewRequest | ExecuteRequest):
    if body.theme is not None:
        return body.theme
    if not (body.theme_id or "").strip():
        raise HTTPException(status_code=400, detail="Provide theme_id or theme")
    themes = get_themes()
    theme = next((t for t in themes if t.theme_id == body.theme_id), None)
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")
    return theme


@app.post("/basket/generate")
def basket_generate(body: GenerateRequest):
    """Generate a basket from a natural-language trend (LLM picks markets + directions + weights)."""
    try:
        theme = generate_basket(body.query, get_kalshi(), OPENAI_API_KEY)
        return theme.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/basket/preview")
def basket_preview(body: PreviewRequest):
    """Preview basket order: estimated cost and contract counts per leg."""
    theme = _resolve_theme(body)
    result = preview(theme, body.total_budget_dollars, body.overrides, get_kalshi())
    return result.model_dump()


@app.post("/basket/execute")
def basket_execute(body: ExecuteRequest):
    """Execute basket order (batched Kalshi orders)."""
    theme = _resolve_theme(body)
    success, message, results = execute(theme, body.total_budget_dollars, body.overrides, get_kalshi())
    legs = [
        BatchOrderResultLeg(
            market_ticker=r.get("market_ticker", "?"),
            client_order_id=r.get("client_order_id"),
            order_id=r.get("order_id"),
            status=r.get("status"),
            error=r.get("error"),
        )
        for r in results
    ]
    return ExecuteResponse(success=success, message=message, legs=legs)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/markets/open")
def list_open_markets(limit: int = 200):
    """List open markets from Kalshi demo (public, no auth)."""
    markets = get_kalshi().get_open_markets(limit=limit)
    return {"markets": markets, "count": len(markets)}


@app.get("/markets")
def get_markets(tickers: str = ""):
    """Fetch specific markets by ticker (comma-separated). Returns list of market objects."""
    if not tickers.strip():
        return {"markets": []}
    ticker_list = [t.strip() for t in tickers.split(",") if t.strip()]
    if not ticker_list:
        return {"markets": []}
    by_ticker = get_kalshi().get_markets(ticker_list)
    return {"markets": [by_ticker[t] for t in ticker_list if t in by_ticker]}


@app.get("/events/search")
def search_events_api(q: Optional[str] = None, limit: int = 20):
    """Search events by keyword. Returns top `limit` by volume. Requires init: python scripts/init_events_db.py"""
    try:
        events = search_events(q=q, limit=limit)
        return {"events": events, "count": len(events)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {e}. Run: python scripts/init_events_db.py")


@app.get("/events/open")
def list_open_events(limit: Optional[int] = None, with_nested_markets: bool = True):
    """List open events from Kalshi demo (public, no auth). Omit limit for full list."""
    events = get_kalshi().get_open_events(limit=limit, with_nested_markets=with_nested_markets)
    return {"events": events, "count": len(events)}


@app.get("/events/by/{event_ticker}")
def get_event_api(event_ticker: str):
    """Get one event by ticker for basket building."""
    ev = get_event(event_ticker)
    if not ev:
        raise HTTPException(status_code=404, detail="Event not found")
    return ev


@app.get("/themes/from-event/{event_ticker}")
def theme_from_event(event_ticker: str):
    """Build a basket theme from an event (for preview/execute)."""
    ev = get_event(event_ticker)
    if not ev:
        raise HTTPException(status_code=404, detail="Event not found")
    markets = ev.get("markets", [])
    if not markets:
        raise HTTPException(status_code=400, detail="Event has no markets")
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
    return {
        "theme_id": ev.get("event_ticker", event_ticker),
        "name": ev.get("title", event_ticker),
        "description": f"Event: {ev.get('title', '')}",
        "legs": legs,
    }


# --- Test skeleton: single-order flow ---


@app.get("/test/hardcoded-market")
def test_hardcoded_market():
    """Return a known open market for testing."""
    return {"ticker": HARDCODED_TICKER, "title": HARDCODED_TITLE}


@app.post("/test/search-market")
def test_search_market(body: dict):
    """LLM picks best matching open market for the query."""
    query = (body.get("query") or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="query required")
    try:
        result = search_market_by_query(get_kalshi(), query, OPENAI_API_KEY)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/test/place-order")
def test_place_order(body: dict):
    """Place 1 contract buy at ask (IOC). Body: { ticker, side?: yes|no }."""
    ticker = (body.get("ticker") or "").strip()
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker required")
    side = (body.get("side") or "yes").lower()
    if side not in ("yes", "no"):
        side = "yes"
    try:
        result = place_order(get_kalshi(), ticker, side=side, count=1)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
