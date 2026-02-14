"""Minimal Streamlit UI for Kalshi ETF Baskets. Run backend first (uvicorn app.main:app)."""
import os
import httpx

import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

DIRECTION_OPTIONS = ["BUY_YES", "BUY_NO", "SELL_YES", "SELL_NO"]


def api_get(path: str):
    with httpx.Client() as client:
        r = client.get(f"{BACKEND_URL}{path}", timeout=10.0)
        r.raise_for_status()
        return r.json()


def api_post(path: str, json_body: dict, timeout: float = 15.0):
    with httpx.Client() as client:
        r = client.post(f"{BACKEND_URL}{path}", json=json_body, timeout=timeout)
        r.raise_for_status()
        return r.json()


def main():
    st.set_page_config(page_title="Kalshi ETF Baskets", layout="wide")
    st.title("Kalshi ETF Baskets")

    try:
        data = api_get("/themes")
    except Exception as e:
        st.error(f"Backend not reachable at {BACKEND_URL}. Start it with: uvicorn app.main:app --reload")
        st.code("cd backend && uvicorn app.main:app --reload", language="bash")
        st.stop()

    fixed_themes = data.get("themes", [])

    # Source: pre-defined or generate from trend
    source = st.radio("Basket source", ["Pre-defined theme", "Generate from trend"], horizontal=True)

    theme = None
    theme_id = None

    if source == "Pre-defined theme":
        if not fixed_themes:
            st.warning("No pre-defined themes configured.")
            st.stop()
        theme_names = [t["name"] for t in fixed_themes]
        choice = st.selectbox("Choose a theme", range(len(fixed_themes)), format_func=lambda i: theme_names[i])
        theme = fixed_themes[choice]
        theme_id = theme["theme_id"]

    else:
        # Generate from trend
        query = st.text_area("Describe your trend or belief", placeholder="e.g. I think AI progress will stall in 2026 and regulation will tighten.")
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

    if theme is None:
        if source == "Generate from trend":
            st.info("Enter a trend above and click **Generate basket**.")
        st.stop()

    st.subheader(theme.get("name", "Basket"))
    st.caption(theme.get("description", ""))

    legs = theme.get("legs", [])
    if not legs:
        st.info("This theme has no legs.")
        st.stop()

    # Overrides state
    if "overrides" not in st.session_state:
        st.session_state.overrides = {}
    key = theme_id
    if key not in st.session_state.overrides:
        st.session_state.overrides[key] = {
            leg["market_ticker"]: {
                "enabled": leg.get("enabled", True),
                "direction": leg.get("direction", "BUY_YES"),
                "weight": leg.get("weight", 1.0 / len(legs)),
            }
            for leg in legs
        }
    overrides = st.session_state.overrides[key]

    total_budget = st.number_input("Basket budget ($)", min_value=1.0, value=50.0, step=5.0)

    st.subheader("Legs")
    cols = st.columns([1, 3, 2, 2, 2, 2])
    with cols[0]:
        st.markdown("**Include**")
    with cols[1]:
        st.markdown("**Market**")
    with cols[2]:
        st.markdown("**Direction**")
    with cols[3]:
        st.markdown("**Weight %**")
    with cols[4]:
        st.markdown("**Est. $**")
    with cols[5]:
        st.markdown("**Warnings**")

    for i, leg in enumerate(legs):
        ticker = leg["market_ticker"]
        o = overrides.get(ticker, {})
        with st.container():
            c0, c1, c2, c3, c4, c5 = st.columns([1, 3, 2, 2, 2, 2])
            with c0:
                enabled = st.checkbox("", value=o.get("enabled", True), key=f"en_{key}_{ticker}")
                overrides[ticker] = overrides.get(ticker, {})
                overrides[ticker]["enabled"] = enabled
            with c1:
                st.caption(leg.get("title", ticker))
            with c2:
                direction = st.selectbox(
                    "Direction",
                    DIRECTION_OPTIONS,
                    index=DIRECTION_OPTIONS.index(o.get("direction", "BUY_YES")),
                    key=f"dir_{key}_{ticker}",
                    label_visibility="collapsed",
                )
                overrides[ticker]["direction"] = direction
            with c3:
                weight = st.slider(
                    "Weight",
                    0.0,
                    100.0,
                    (o.get("weight", 1.0 / len(legs)) * 100),
                    key=f"wt_{key}_{ticker}",
                    label_visibility="collapsed",
                ) / 100.0
                overrides[ticker]["weight"] = weight

    overrides_for_api = {
        ticker: {"enabled": o.get("enabled", True), "direction": o.get("direction", "BUY_YES"), "weight": o.get("weight", 0)}
        for ticker, o in overrides.items()
    }

    # Payload: for generated theme send full theme; for fixed send theme_id
    preview_payload = {
        "theme_id": theme_id,
        "total_budget_dollars": total_budget,
        "overrides": overrides_for_api,
    }
    execute_payload = {
        "theme_id": theme_id,
        "total_budget_dollars": total_budget,
        "overrides": overrides_for_api,
    }
    if theme_id == "generated" and theme:
        preview_payload["theme"] = theme
        execute_payload["theme"] = theme

    if st.button("Preview"):
        try:
            pre = api_post("/basket/preview", preview_payload)
            st.subheader("Preview")
            st.metric("Est. total cost", f"${pre.get('est_total_cost_dollars', 0):.2f}")
            for pl in pre.get("legs", []):
                with st.expander(f"{pl.get('title', pl.get('market_ticker'))} — {pl.get('contracts', 0)} contracts @ ${pl.get('price_dollars', 0):.2f}"):
                    st.write(f"Est. cost: ${pl.get('est_cost_dollars', 0):.2f}")
                    if pl.get("warnings"):
                        st.warning(" ".join(pl["warnings"]))
            if pre.get("warnings"):
                st.warning(" ".join(pre["warnings"]))
            st.session_state.last_preview = pre
        except httpx.HTTPStatusError as e:
            st.error(f"Preview failed: {e.response.text}")
        except Exception as e:
            st.error(str(e))

    if st.button("Execute basket", type="primary"):
        try:
            result = api_post("/basket/execute", execute_payload)
            if result.get("success"):
                st.success(result.get("message", "Done."))
            else:
                st.error(result.get("message", "Execution failed."))
            for leg in result.get("legs", []):
                st.write(f"**{leg.get('market_ticker')}**: order_id={leg.get('order_id')} status={leg.get('status')} error={leg.get('error')}")
        except httpx.HTTPStatusError as e:
            st.error(f"Execute failed: {e.response.text}")
        except Exception as e:
            st.error(str(e))


if __name__ == "__main__":
    main()
