# Kalshi ETF Baskets (TreeHacks MVP)

Trade a basket of Kalshi markets in one action: pick a theme, set direction and weights per leg, preview, then execute as a batched order.

## Setup

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

Create a `.env` in `backend/` (or set env vars):

```env
KALSHI_BASE_URL=https://demo-api.kalshi.co
KALSHI_API_KEY_ID=your-api-key-id
KALSHI_PRIVATE_KEY_PATH=./kalshi_private.key
```

Put your Kalshi private key in `backend/kalshi_private.key` (PEM format). For demo, use [Kalshi demo](https://demo.kalshi.com/) and create an API key under Account & security → API Keys.

### Themes (placeholder tickers)

`backend/themes.json` uses **placeholder market tickers**. Replace them with real Kalshi tickers that are currently open:

1. List open markets: `GET https://demo-api.kalshi.co/trade-api/v2/markets?status=open&limit=50`
2. Pick tickers and set `market_ticker` and `event_ticker` in each leg in `themes.json`.

### Run

**Terminal 1 – API**

```bash
cd backend
uvicorn app.main:app --reload
```

**Terminal 2 – UI**

```bash
cd frontend
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Open http://localhost:8501. Use "Choose a basket theme", set budget and per-leg direction/weights, then **Preview** and **Execute basket**.

## API (fixed themes only)

- `GET /themes` – list themes
- `GET /themes/{theme_id}` – one theme
- `POST /basket/preview` – body: `{ "theme_id", "total_budget_dollars", "overrides": { "TICKER": { "enabled", "direction", "weight" } } }`
- `POST /basket/execute` – same body, places batched orders (IOC, max 20 legs)

## Project layout

```
treehacks/
  backend/
    app/
      main.py           # FastAPI
      config.py
      kalshi_client.py  # RSA signing + markets + batch orders
      basket_service.py # preview / execute
      models.py
    themes.json
    requirements.txt
  frontend/
    streamlit_app.py
    requirements.txt
```

**LLM basket:** Use "Generate from trend" in the UI: describe your view (e.g. "AI progress will stall in 2026"), click Generate basket. The app fetches open Kalshi markets and uses OpenAI to pick 5–10 markets with directions and weights. Then preview/execute as usual. Requires `OPENAI_API_KEY` in `backend/.env`.
