"""FastAPI app: themes and basket preview/execute."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException

from app.basket_service import execute, preview
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
