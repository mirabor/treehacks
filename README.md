# BetBasket

**Trade prediction-market baskets like ETFs — one click, multiple markets.**

Built at [TreeHacks](https://www.treehacks.com/) 2026.

---

## The Idea

Prediction markets (like [Kalshi](https://kalshi.com)) let you bet on real-world outcomes — elections, Fed policy, AI milestones, sports. But placing individual bets across many markets is tedious. What if you could:

- **Pick a theme** — e.g., "AI stagnation in 2026"
- **Build a basket** — 5–10 related markets with one click
- **Trade the whole basket** — set a budget, preview cost, execute

Think of it as an **ETF for prediction markets**: diversify across a thesis instead of one-off contracts.

---

## What We Built

### Three Ways to Build a Basket

| Source | How it works |
|--------|--------------|
| **Pre-defined theme** | Curated trend baskets: AI Stagnation, Trump Economic Agenda, Climate Goals, Cannabis Policy |
| **Generate from trend** | Describe a belief in plain English → GPT-4o-mini picks markets and directions |
| **Search events** | Browse top events by volume, search by keyword, use any event as a basket |

### UX Features

- **For / Against toggle** — Flip the whole basket from betting on the trend to betting against it
- **Yes / No per leg** — Simple labels instead of BUY_YES/BUY_NO/SELL_YES/SELL_NO
- **Preview before execute** — See estimated cost, contracts, and orderbook before placing orders
- **Weighted legs** — Adjust allocation per market (default: equal weight)

### Tech Highlights

- **SQLite events DB** — Searchable index of 50k+ Kalshi events by volume
- **Keyword expansion** — "AI" → OpenAI, xAI, ChatGPT, Anthropic for smarter search
- **Structured output** — LLM returns JSON with market tickers, directions, weights (validated against candidate set)

---

## Tech Stack

| Layer | Tech |
|-------|------|
| **Backend** | FastAPI, Pydantic |
| **Frontend** | Streamlit |
| **Database** | SQLite (events index) |
| **LLM** | OpenAI GPT-4o-mini (structured output) |
| **API** | Kalshi demo (RSA-signed requests) |

---

## Technical Challenges & How We Solved Them

### 1. **Matching natural language to markets**

**Problem:** User says "AI progress will stall" — how do we find relevant markets among 50k+ events?

**Solution:** Keyword extraction + expansion. Short terms like "ai" expand to ["OpenAI", "xAI", "ChatGPT", "Anthropic"] so we search the events DB for each. We batch-fetch full market data from Kalshi and pass ~80 candidates to the LLM with tickers, titles, and rules.

### 2. **LLM hallucinating tickers**

**Problem:** The model might invent tickers that don't exist or are closed.

**Solution:** Strict schema + validation. We use `response_format` with a JSON schema so the model returns only `market_ticker`, `direction`, `weight`. We filter each leg: if the ticker isn't in our candidate set, we drop it. No hallucinated contracts reach the basket.

### 3. **Unified direction UX (For/Against vs Yes/No)**

**Problem:** BUY_YES, BUY_NO, SELL_YES, SELL_NO are confusing. Users think in terms of "I bet on this" or "I bet against this."

**Solution:** Two-level abstraction. A global **For / Against** toggle flips all legs (BUY_YES ↔ BUY_NO, SELL_YES ↔ SELL_NO). Per-leg we display **Yes / No** — betting the outcome happens or doesn't. Internally we still send Kalshi’s 4-direction enum.

### 4. **Events DB vs live API**

**Problem:** Kalshi’s API returns events with nested markets, but searching by keyword isn’t supported. We need volume-ordered, searchable events.

**Solution:** One-time init script fetches all open events, parses market tickers, stores in SQLite with `title`, `volume`, `markets_json`. Search uses SQL `LIKE` on title/series/category. Generate-from-trend and Search share the same event pool.

### 5. **Batch orders and pricing**

**Problem:** Each leg needs a price (ask for buy, bid for sell). Orders are GTC resting orders.

**Solution:** `basket_service` fetches markets in batches, applies overrides (direction, weight, enabled), computes per-leg budget and contract counts, builds Kalshi batch order payload. Preview shows est. cost before execute.

---

## How to Run

### Prerequisites

- Python 3.9+
- [Kalshi demo](https://demo.kalshi.com/) account (no real money)
- Optional: [OpenAI API key](https://platform.openai.com/) for "Generate from trend"

### 1. Clone & install

```bash
git clone <your-repo-url>
cd treehacks
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
pip install -r frontend/requirements.txt
```

### 2. Configure

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env`:

| Variable | Required for | Where to get |
|----------|--------------|--------------|
| `KALSHI_API_KEY_ID` | All | Kalshi demo → Account & security → API Keys |
| `KALSHI_PRIVATE_KEY_PATH` | All | Same page — download PEM, save as `backend/kalshi_private.key` |
| `OPENAI_API_KEY` | Generate from trend | [platform.openai.com](https://platform.openai.com/api-keys) |

### 3. Initialize events DB (required for search & generate)

```bash
cd backend
python scripts/init_events_db.py
```

Creates `events.db` with open events indexed by volume. Run once after clone; re-run if markets change.

### 4. Start the app

**Terminal 1 — API**

```bash
cd backend
uvicorn app.main:app --reload
```

**Terminal 2 — UI**

```bash
cd frontend
streamlit run streamlit_app.py
```

Open **http://localhost:8501**.

---

## Project Structure

```
treehacks/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI routes
│   │   ├── basket_service.py # Preview & execute
│   │   ├── llm_basket_service.py  # Generate from trend (LLM)
│   │   ├── events_db.py      # SQLite search
│   │   ├── kalshi_client.py  # RSA auth, markets, orders
│   │   └── models.py
│   ├── scripts/
│   │   ├── init_events_db.py # Populate events DB
│   │   └── build_themes_from_events.py
│   ├── themes.json           # Pre-defined trend baskets
│   └── requirements.txt
├── frontend/
│   ├── streamlit_app.py
│   └── requirements.txt
└── README.md
```

---

## License

MIT.

---

*Uses [Kalshi demo](https://demo.kalshi.com/) — no real money. Trade at your own risk.*
