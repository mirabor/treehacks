"""Basket preview and execute using themes and Kalshi client."""
from __future__ import annotations

import uuid
from typing import Any, Optional

from app.kalshi_client import KalshiClient
from app.models import (
    BasketLeg,
    BasketOrderPreview,
    BasketOrderPreviewLeg,
    BasketTheme,
    Direction,
    LegOverride,
)

TRADABLE_STATUSES = {"active", "open"}
BATCH_ORDER_LIMIT = 20


def _parse_dollars(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).strip())
    except (ValueError, TypeError):
        return None


def _is_tradable(market: dict) -> bool:
    status = (market.get("status") or "").lower()
    return status in TRADABLE_STATUSES


def _pick_price_dollars(market: dict, direction: Direction) -> Optional[float]:
    """Return price in dollars for the given direction (ask for buy, bid for sell)."""
    if direction == "BUY_YES":
        return _parse_dollars(market.get("yes_ask_dollars"))
    if direction == "SELL_YES":
        return _parse_dollars(market.get("yes_bid_dollars"))
    if direction == "BUY_NO":
        return _parse_dollars(market.get("no_ask_dollars"))
    if direction == "SELL_NO":
        return _parse_dollars(market.get("no_bid_dollars"))
    return None


def _apply_overrides(legs: list[BasketLeg], overrides: dict[str, LegOverride]) -> list[BasketLeg]:
    out = []
    for leg in legs:
        o = overrides.get(leg.market_ticker)
        if not o:
            out.append(leg.model_copy(deep=True))
            continue
        d = leg.model_dump()
        if o.enabled is not None:
            d["enabled"] = o.enabled
        if o.direction is not None:
            d["direction"] = o.direction
        if o.weight is not None:
            d["weight"] = max(0.0, min(1.0, o.weight))
        out.append(BasketLeg(**d))
    return out


def _normalize_weights(legs: list[BasketLeg]) -> None:
    enabled = [l for l in legs if l.enabled]
    total = sum(l.weight for l in enabled)
    if total <= 0:
        return
    for l in enabled:
        l.weight /= total


def preview(
    theme: BasketTheme,
    total_budget_dollars: float,
    overrides: dict[str, LegOverride],
    kalshi: KalshiClient,
) -> BasketOrderPreview:
    legs = _apply_overrides(theme.legs, overrides)
    enabled = [l for l in legs if l.enabled]
    if not enabled:
        return BasketOrderPreview(
            total_budget_dollars=total_budget_dollars,
            legs=[],
            est_total_cost_dollars=0.0,
            warnings=["No legs enabled."],
        )
    _normalize_weights(legs)
    tickers = [l.market_ticker for l in enabled]
    snapshots = kalshi.get_markets(tickers)
    preview_legs: list[BasketOrderPreviewLeg] = []
    all_warnings: list[str] = []

    for leg in enabled:
        m = snapshots.get(leg.market_ticker)
        leg_warnings: list[str] = []
        if not m:
            preview_legs.append(
                BasketOrderPreviewLeg(
                    market_ticker=leg.market_ticker,
                    title=leg.title,
                    direction=leg.direction,
                    price_dollars=0.0,
                    contracts=0,
                    est_cost_dollars=0.0,
                    warnings=["Market not found."],
                )
            )
            continue
        if not _is_tradable(m):
            leg_warnings.append(f"Market not tradable (status={m.get('status')}).")
        price = _pick_price_dollars(m, leg.direction)
        if price is None or price <= 0:
            leg_warnings.append("Missing or invalid bid/ask.")
            preview_legs.append(
                BasketOrderPreviewLeg(
                    market_ticker=leg.market_ticker,
                    title=leg.title,
                    direction=leg.direction,
                    price_dollars=0.0,
                    contracts=0,
                    est_cost_dollars=0.0,
                    warnings=leg_warnings,
                )
            )
            continue
        leg_budget = total_budget_dollars * leg.weight
        contracts = int(leg_budget // price)
        if contracts < 1:
            leg_warnings.append("Budget too small for at least 1 contract.")
        cost = contracts * price if contracts >= 1 else 0.0
        preview_legs.append(
            BasketOrderPreviewLeg(
                market_ticker=leg.market_ticker,
                title=leg.title,
                direction=leg.direction,
                price_dollars=price,
                contracts=max(0, contracts),
                est_cost_dollars=round(cost, 4),
                warnings=leg_warnings,
            )
        )

    est_total = sum(p.est_cost_dollars for p in preview_legs)
    return BasketOrderPreview(
        total_budget_dollars=total_budget_dollars,
        legs=preview_legs,
        est_total_cost_dollars=round(est_total, 4),
        warnings=all_warnings,
    )


def _to_kalshi_order(leg: BasketOrderPreviewLeg, direction: Direction, basket_id: str) -> Optional[dict]:
    if leg.contracts <= 0:
        return None
    # Kalshi accepts yes_price_dollars / no_price_dollars as fixed-point strings
    price_str = f"{leg.price_dollars:.4f}".rstrip("0").rstrip(".")
    if "." not in price_str:
        price_str = f"{price_str}.0"
    is_yes = direction in ("BUY_YES", "SELL_YES")
    action = "buy" if "BUY" in direction else "sell"
    req: dict = {
        "ticker": leg.market_ticker,
        "side": "yes" if is_yes else "no",
        "action": action,
        "count": leg.contracts,
        "client_order_id": f"{basket_id}:{leg.market_ticker}:{uuid.uuid4().hex[:8]}",
        "time_in_force": "immediate_or_cancel",
    }
    if is_yes:
        req["yes_price_dollars"] = price_str
    else:
        req["no_price_dollars"] = price_str
    return req


def execute(
    theme: BasketTheme,
    total_budget_dollars: float,
    overrides: dict[str, LegOverride],
    kalshi: KalshiClient,
) -> tuple[bool, str, list[dict]]:
    """Returns (success, message, list of per-leg result dicts)."""
    pre = preview(theme, total_budget_dollars, overrides, kalshi)
    to_send = [
        _to_kalshi_order(leg, leg.direction, theme.theme_id)
        for leg in pre.legs
        if leg.contracts > 0
    ]
    to_send = [x for x in to_send if x is not None]
    if not to_send:
        return False, "No orders to place (all legs have 0 contracts or errors).", []
    if len(to_send) > BATCH_ORDER_LIMIT:
        return False, f"Too many legs (max {BATCH_ORDER_LIMIT}).", []

    try:
        resp = kalshi.batch_create_orders(to_send)
    except Exception as e:
        return False, str(e), []

    results = []
    for item in resp.get("orders", []):
        err = item.get("error")
        order = item.get("order")
        client_id = item.get("client_order_id")
        ticker = None
        if order:
            ticker = order.get("ticker")
        elif to_send and client_id:
            for o in to_send:
                if o.get("client_order_id") == client_id:
                    ticker = o.get("ticker")
                    break
        results.append({
            "market_ticker": ticker or "?",
            "client_order_id": client_id,
            "order_id": order.get("order_id") if order else None,
            "status": order.get("status") if order else None,
            "error": err.get("message") if isinstance(err, dict) else str(err) if err else None,
        })
    success = not any(r.get("error") for r in results)
    msg = "Batch submitted." if success else "Some orders failed; check per-leg results."
    return success, msg, results
