"""Minimal test UI: Buy 1 contract on hardcoded or LLM-found market. Run backend first."""
import os
import httpx

import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")


def api_get(path: str):
    with httpx.Client() as client:
        r = client.get(f"{BACKEND_URL}{path}", timeout=10.0)
        r.raise_for_status()
        return r.json()


def api_post(path: str, json_body: dict, timeout: float = 30.0):
    with httpx.Client() as client:
        r = client.post(f"{BACKEND_URL}{path}", json=json_body, timeout=timeout)
        r.raise_for_status()
        return r.json()


def main():
    st.set_page_config(page_title="Test Buy", layout="centered")
    st.title("Test: Single Contract Buy")

    try:
        api_get("/health")
    except Exception:
        st.error(f"Backend not reachable at {BACKEND_URL}. Start it: cd backend && uvicorn app.main:app --reload")
        st.stop()

    # --- Hardcoded market ---
    st.subheader("1. Hardcoded market")
    try:
        h = api_get("/test/hardcoded-market")
        ticker = h.get("ticker", "?")
        title = h.get("title", ticker)
    except Exception as e:
        st.error(str(e))
        ticker = None
        title = None

    if ticker:
        st.write(f"**{title}**")
        st.caption(f"Ticker: `{ticker}`")
        if st.button("Buy 1 YES contract (hardcoded)", type="primary", key="buy_hardcoded"):
            try:
                result = api_post("/test/place-order", {"ticker": ticker, "side": "yes"})
                if result.get("success"):
                    st.success(f"Order placed: {result.get('order_id')} | Status: {result.get('status')}")
                    st.info("Check your Kalshi demo dashboard — Positions or Resting.")
                else:
                    st.error(result.get("error", "Order failed"))
            except httpx.HTTPStatusError as e:
                st.error(e.response.text)
            except Exception as e:
                st.error(str(e))

    st.divider()

    # --- LLM search ---
    st.subheader("2. AI search: find market by query")
    query = st.text_input("Query", value="AI progress by OpenAI", key="query")
    if st.button("Search", key="search"):
        if not (query or "").strip():
            st.warning("Enter a query.")
        else:
            with st.spinner("Searching..."):
                try:
                    m = api_post("/test/search-market", {"query": query.strip()}, timeout=45.0)
                    st.session_state.ai_ticker = m.get("ticker")
                    st.session_state.ai_title = m.get("title", m.get("ticker"))
                except httpx.HTTPStatusError as e:
                    st.error(e.response.text)
                except Exception as e:
                    st.error(str(e))

    if "ai_ticker" in st.session_state:
        st.write(f"**{st.session_state.ai_title}**")
        st.caption(f"Ticker: `{st.session_state.ai_ticker}`")
        if st.button("Buy 1 YES contract (AI match)", type="primary", key="buy_ai"):
            try:
                result = api_post(
                    "/test/place-order",
                    {"ticker": st.session_state.ai_ticker, "side": "yes"},
                )
                if result.get("success"):
                    st.success(f"Order placed: {result.get('order_id')} | Status: {result.get('status')}")
                    st.info("Check your Kalshi demo dashboard — Positions or Resting.")
                else:
                    st.error(result.get("error", "Order failed"))
            except httpx.HTTPStatusError as e:
                st.error(e.response.text)
            except Exception as e:
                st.error(str(e))


if __name__ == "__main__":
    main()
