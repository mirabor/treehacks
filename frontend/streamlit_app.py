"""BetBasket — Trade themed baskets of prediction markets. Run backend first."""
from __future__ import annotations

import os
from datetime import datetime

import httpx
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

def _flip_direction(d: str) -> str:
    """Flip direction: For ↔ Against the outcome."""
    flip = {"BUY_YES": "BUY_NO", "BUY_NO": "BUY_YES", "SELL_YES": "SELL_NO", "SELL_NO": "SELL_YES"}
    return flip.get(d, "BUY_YES")


def _direction_to_yes_no(d: str) -> str:
    """Map Kalshi direction to Yes/No label (betting on outcome or against)."""
    return "Yes" if d in ("BUY_YES", "SELL_NO") else "No"


def api_get(path: str, params: dict | None = None):
    with httpx.Client() as client:
        r = client.get(f"{BACKEND_URL}{path}", params=params or {}, timeout=30.0)
        r.raise_for_status()
        return r.json()


def _fetch_market(ticker: str) -> dict | None:
    """Fetch a single market by ticker; returns None on error."""
    try:
        data = api_get("/markets", params={"tickers": ticker})
        markets = data.get("markets", [])
        return markets[0] if markets else None
    except Exception:
        return None


def api_post(path: str, json_body: dict, timeout: float = 15.0):
    with httpx.Client() as client:
        r = client.post(f"{BACKEND_URL}{path}", json=json_body, timeout=timeout)
        r.raise_for_status()
        return r.json()


def _format_close_time(close_time: str | None) -> str:
    if not close_time:
        return "—"
    try:
        dt = datetime.fromisoformat(close_time.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y %H:%M UTC")
    except Exception:
        return str(close_time)[:19]


def _format_price(val: str | int | float | None) -> str:
    """Format a price value for display; return '—' if invalid."""
    if val is None or val == "":
        return "—"
    try:
        f = float(str(val).strip())
        return f"${f:.2f}"
    except (ValueError, TypeError):
        return "—"


def _format_volume(vol: int) -> str:
    if vol >= 1_000_000:
        return f"${vol/1e6:.1f}M"
    if vol >= 1_000:
        return f"${vol/1e3:.1f}K"
    return str(vol)


def _render_market_details(m: dict, *, show_orderbook: bool = True) -> None:
    """Render full Kalshi-style market details (same info as demo UI)."""
    ticker = m.get("ticker") or m.get("market_ticker", "")
    event_ticker = m.get("event_ticker", "")

    st.markdown("**Market info**")
    cols = st.columns([2, 2, 2])
    with cols[0]:
        st.caption(f"Ticker: `{ticker}`")
    with cols[1]:
        if event_ticker:
            st.caption(f"Event: `{event_ticker}`")
    with cols[2]:
        status = m.get("status", "")
        if status:
            st.caption(f"Status: **{status}**")

    open_time = m.get("open_time")
    close_time = m.get("close_time")
    exp_time = m.get("latest_expiration_time") or m.get("expiration_time")
    if open_time or close_time or exp_time:
        st.caption(
            f"Opens: {_format_close_time(open_time)} | "
            f"Closes: {_format_close_time(close_time)} | "
            f"Expires: {_format_close_time(exp_time)}"
        )

    if show_orderbook:
        st.markdown("**Orderbook**")
        ya_f = _format_price(m.get("yes_ask_dollars"))
        yb_f = _format_price(m.get("yes_bid_dollars"))
        na_f = _format_price(m.get("no_ask_dollars"))
        nb_f = _format_price(m.get("no_bid_dollars"))
        st.markdown(
            "| Side | Bid (sell at) | Ask (buy at) |\n|------|---------------|--------------|\n"
            f"| YES  | {yb_f} | {ya_f} |\n| NO   | {nb_f} | {na_f} |"
        )

    vol = m.get("volume") or m.get("volume_fp")
    vol_24h = m.get("volume_24h") or m.get("volume_24h_fp")
    liq = m.get("liquidity_dollars") or m.get("liquidity")
    last = m.get("last_price_dollars") or m.get("last_price")
    oi = m.get("open_interest") or m.get("open_interest_fp")
    if vol is not None or vol_24h is not None or liq is not None or last is not None or oi is not None:
        st.markdown("**Market stats**")
        stat_parts = []
        if vol is not None:
            stat_parts.append(f"Volume: {vol}")
        if vol_24h is not None:
            stat_parts.append(f"24h vol: {vol_24h}")
        if liq is not None:
            try:
                lf = float(str(liq).strip())
                stat_parts.append(f"Liquidity: ${lf:.2f}")
            except (ValueError, TypeError):
                stat_parts.append(f"Liquidity: {liq}")
        if last is not None:
            stat_parts.append(f"Last: {_format_price(last)}")
        if oi is not None:
            stat_parts.append(f"Open interest: {oi}")
        st.caption(" | ".join(stat_parts))

    yes_sub = m.get("yes_sub_title") or ""
    no_sub = m.get("no_sub_title") or ""
    if yes_sub or no_sub:
        st.markdown("**Contract meanings**")
        st.caption(f"YES = {yes_sub or '—'} | NO = {no_sub or '—'}")

    subtitle = m.get("subtitle", "")
    if subtitle:
        st.caption(f"*{subtitle}*")

    rules = m.get("rules_primary", "")
    rules2 = m.get("rules_secondary", "")
    if rules:
        st.markdown("**Settlement rules**")
        st.markdown(rules)
    if rules2:
        st.caption(rules2[:500] + ("…" if len(rules2 or "") > 500 else ""))

    result = m.get("result", "")
    if result:
        st.info(f"**Result:** {result.upper()}")

    st.markdown(f"[View on Kalshi demo →](https://demo.kalshi.com/markets/{ticker})")


st.set_page_config(page_title="BetBasket", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .stApp { max-width: 1200px; margin: 0 auto; }
    h1 { color: #1a1a2e; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

st.title("BetBasket")
st.markdown("Search events, build a basket, and trade in one click.")

try:
    api_get("/health")
except Exception:
    st.error(f"Backend not reachable at {BACKEND_URL}. Start: `uvicorn app.main:app --reload`")
    st.code("cd backend && uvicorn app.main:app --reload", language="bash")
    st.stop()

# --- Unified flow: search + themes + generate ---
source = st.radio("Basket source", ["Pre-defined theme", "Generate from trend", "Search events"], horizontal=True)

theme = None
theme_id = None

# 1. Search events (top 20 by volume, filter by keyword)
if source == "Search events":
    if "selected_theme" in st.session_state and "selected_theme_id" in st.session_state:
        theme = st.session_state.selected_theme
        theme_id = st.session_state.selected_theme_id
    else:
        search_q = st.text_input(
            "Search by keyword (e.g. Fed, NBA, Democratic)",
            key="event_search",
            placeholder="Leave empty for top 20 traded events...",
        )
        try:
            data = api_get("/events/search", params={"q": (search_q or "").strip(), "limit": 20})
        except Exception as e:
            st.error(str(e))
            data = {"events": [], "count": 0}

        events = data.get("events", [])
        if events:
            st.caption(f"Top 20 events by volume" + (f" matching '{search_q}'" if search_q else ""))
            for ev in events:
                title = (ev.get("title") or ev.get("event_ticker", ""))[:70]
                vol = ev.get("volume", 0)
                mcount = ev.get("market_count", 0)
                et = ev.get("event_ticker", "")
                cols = st.columns([4, 1, 1])
                with cols[0]:
                    st.markdown(f"**{title}**")
                with cols[1]:
                    st.caption(f"{mcount} markets")
                with cols[2]:
                    st.caption(_format_volume(vol))
                if st.button("Use as basket", key=f"use_{et}"):
                    try:
                        theme = api_get(f"/themes/from-event/{et}")
                        theme_id = theme.get("theme_id", et)
                        st.session_state.selected_theme = theme
                        st.session_state.selected_theme_id = theme_id
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
                st.divider()
        else:
            st.info("No events found. Run `python scripts/init_events_db.py` in backend to populate the database.")

# 2. Pre-defined theme
elif source == "Pre-defined theme":
    try:
        data = api_get("/themes")
    except Exception:
        st.error("Could not load themes.")
        st.stop()
    fixed_themes = data.get("themes", [])
    if not fixed_themes:
        st.warning("No pre-defined themes configured.")
    else:
        theme_names = [t["name"] for t in fixed_themes]
        choice = st.selectbox("Choose a theme", range(len(fixed_themes)), format_func=lambda i: theme_names[i])
        theme = fixed_themes[choice]
        theme_id = theme["theme_id"]

# 3. Generate from trend
else:
    query = st.text_area("Describe your trend or belief", placeholder="e.g. I think AI progress will stall in 2026.")
    if st.button("Generate basket"):
        if not query.strip():
            st.warning("Enter a trend or belief first.")
        else:
            with st.spinner("Fetching markets and generating basket..."):
                try:
                    theme = api_post("/basket/generate", {"query": query.strip()}, timeout=60.0)
                    theme_id = theme.get("theme_id", "generated")
                    st.session_state.generated_theme = theme
                    st.success(f"Generated: **{theme.get('name', 'Basket')}**")
                except httpx.HTTPStatusError as e:
                    st.error(f"Generate failed: {e.response.text}")
                except Exception as e:
                    st.error(str(e))
    if "generated_theme" in st.session_state:
        theme = st.session_state.generated_theme
        theme_id = theme.get("theme_id", "generated")

# --- Basket builder (markets, weights, preview, execute) ---
if theme is None:
    if source == "Generate from trend":
        st.info("Enter a trend above and click **Generate basket**.")
    st.stop()

if source == "Search events" and "selected_theme" in st.session_state:
    if st.button("← Search again", key="clear_search_theme"):
        for k in ("selected_theme", "selected_theme_id"):
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()

st.divider()
st.subheader(theme.get("name", "Basket"))
st.caption(theme.get("description", ""))

legs = theme.get("legs", [])
if not legs:
    st.info("This theme has no legs.")
    st.stop()

if "overrides" not in st.session_state:
    st.session_state.overrides = {}
key = theme_id
if key not in st.session_state.overrides:
    st.session_state.overrides[key] = {
        f"{leg['market_ticker']}_{i}": {
            "enabled": leg.get("enabled", True),
            "direction": leg.get("direction", "BUY_YES"),
            "weight": leg.get("weight", 1.0 / len(legs)),
        }
        for i, leg in enumerate(legs)
    }
overrides = st.session_state.overrides[key]

# Trend direction: For (bet on trend) or Against (bet against)
trend_dir = st.radio(
    "Trend direction",
    ["For", "Against"],
    horizontal=True,
    help="For = bet the trend plays out. Against = bet the opposite.",
    key=f"trend_dir_{key}",
)
bet_against = trend_dir == "Against"

total_budget = st.number_input("Basket budget ($)", min_value=1.0, value=50.0, step=5.0, key="budget")

st.subheader("Markets")
for i, leg in enumerate(legs):
    ticker = leg["market_ticker"]
    leg_key = f"{ticker}_{i}"
    o = overrides.get(ticker, overrides.get(leg_key, {}))
    base_direction = leg.get("direction", "BUY_YES")
    direction = _flip_direction(base_direction) if bet_against else base_direction
    yes_no = _direction_to_yes_no(direction)
    with st.expander(f"**{leg.get('title', ticker)}** — {yes_no}", expanded=True):
        cols = st.columns([2, 2])
        with cols[0]:
            enabled = st.checkbox("Include", value=o.get("enabled", True), key=f"en_{key}_{leg_key}")
        overrides[leg_key] = overrides.get(leg_key, {})
        overrides[leg_key]["enabled"] = enabled
        with cols[1]:
            weight = st.slider(
                "Weight %",
                0.0, 100.0,
                (o.get("weight", 1.0 / len(legs)) * 100),
                key=f"wt_{key}_{leg_key}",
            ) / 100.0
            overrides[leg_key]["weight"] = weight
        st.caption(f"Ticker: `{ticker}`")
        with st.expander("More details (same as Kalshi demo)", expanded=False):
            m = _fetch_market(ticker)
            if m:
                _render_market_details(m)
            else:
                st.caption("Could not load market details.")
                st.markdown(f"[View on Kalshi demo →](https://demo.kalshi.com/markets/{ticker})")

default_weight = 1.0 / len(legs) if legs else 0
overrides_for_api = {}
for i, leg in enumerate(legs):
    ticker = leg["market_ticker"]
    leg_key = f"{ticker}_{i}"
    o = overrides.get(leg_key, overrides.get(ticker, {}))
    base_direction = leg.get("direction", "BUY_YES")
    direction = _flip_direction(base_direction) if bet_against else base_direction
    w = o.get("weight")
    if w is None or (isinstance(w, (int, float)) and w <= 0):
        w = leg.get("weight", default_weight)
    overrides_for_api[ticker] = {"enabled": o.get("enabled", True), "direction": direction, "weight": w}

preview_payload = {"theme_id": theme_id, "total_budget_dollars": total_budget, "overrides": overrides_for_api}
execute_payload = {"theme_id": theme_id, "total_budget_dollars": total_budget, "overrides": overrides_for_api}
# Always pass theme so backend has full legs (avoids theme_id lookup and ensures all legs are present)
if theme:
    preview_payload["theme"] = theme
    execute_payload["theme"] = theme

col_preview, col_exec = st.columns(2)
with col_preview:
    if st.button("Preview", use_container_width=True):
        try:
            pre = api_post("/basket/preview", preview_payload)
            st.session_state.last_preview = pre
        except httpx.HTTPStatusError as e:
            st.error(f"Preview failed: {e.response.text}")
        except Exception as e:
            st.error(str(e))

with col_exec:
    if st.button("Execute basket", type="primary", use_container_width=True):
        try:
            result = api_post("/basket/execute", execute_payload)
            st.session_state.last_execute = result
        except httpx.HTTPStatusError as e:
            st.error(f"Execute failed: {e.response.text}")
        except Exception as e:
            st.error(str(e))

if "last_preview" in st.session_state:
    pre = st.session_state.last_preview
    st.divider()
    st.subheader("Preview")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Est. total cost", f"${pre.get('est_total_cost_dollars', 0):.2f}")
    with col2:
        total_contracts = sum(p.get("contracts", 0) for p in pre.get("legs", []))
        st.metric("Total contracts", total_contracts)
    with col3:
        st.metric("Order type", "Resting (GTC)")
    legs_with_orders = sum(1 for p in pre.get("legs", []) if (p.get("contracts") or 0) > 0)
    legs_skipped = len(pre.get("legs", [])) - legs_with_orders
    if legs_skipped > 0:
        st.caption(f"{legs_with_orders} of {len(pre.get('legs', []))} legs have orders; {legs_skipped} skipped (market closed or no bid/ask).")
    st.caption("Orders will rest on the book until filled or canceled.")
    for pl in pre.get("legs", []):
        title = pl.get("title", pl.get("market_ticker"))
        contracts = pl.get("contracts", 0)
        price = pl.get("price_dollars", 0)
        cost = pl.get("est_cost_dollars", 0)
        warnings = pl.get("warnings", [])
        pl_dict = {
            "market_ticker": pl.get("market_ticker"),
            "yes_bid_dollars": pl.get("yes_bid_dollars"),
            "yes_ask_dollars": pl.get("yes_ask_dollars"),
            "no_bid_dollars": pl.get("no_bid_dollars"),
            "no_ask_dollars": pl.get("no_ask_dollars"),
            "close_time": pl.get("close_time"),
            "rules_primary": pl.get("rules_primary"),
        }
        with st.expander(f"{title} — {contracts} contracts @ ${price:.2f} (est. ${cost:.2f})", expanded=contracts > 0):
            if warnings:
                st.warning(" ".join(warnings))
            _render_market_details(pl_dict)
    if pre.get("warnings"):
        st.warning(" ".join(pre["warnings"]))

if "last_execute" in st.session_state:
    result = st.session_state.last_execute
    st.divider()
    st.subheader("Execution result")
    if result.get("success"):
        st.success(result.get("message", "Done."))
    else:
        st.error(result.get("message", "Execution failed."))
    for leg in result.get("legs", []):
        tid = leg.get("market_ticker")
        oid = leg.get("order_id")
        status = leg.get("status")
        err = leg.get("error")
        st.write(f"**{tid}** — order_id: `{oid}` | status: {status}" + (f" | error: {err}" if err else ""))
    st.info("Check your [Kalshi demo dashboard](https://demo.kalshi.com) for Positions and Resting orders.")
