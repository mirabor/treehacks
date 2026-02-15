# Setup (fresh repo) — Mac

Copy-paste these. One venv for the whole project.

### 1. Clone and venv

```bash
cd treehacks
python3 -m venv treehacks2026
source treehacks2026/bin/activate
```

### 2. Install deps

```bash
pip install -r backend/requirements.txt
pip install -r frontend/requirements.txt
```

### 3. Env file

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env`: set `KALSHI_API_KEY_ID` (from Kalshi → Account & security → API Keys). If you use the key file instead of PEM, set `KALSHI_PRIVATE_KEY_PATH=./kalshi_private.key` and put the `.key` file in `backend/`. For **Generate from trend**, set `OPENAI_API_KEY` (from platform.openai.com).

### 4. Run

**Terminal 1 – API**

```bash
cd backend
source ../treehacks2026/bin/activate
uvicorn app.main:app --reload
```

**Terminal 2 – UI**

```bash
cd frontend
source ../treehacks2026/bin/activate
streamlit run streamlit_app.py
```

Then open **http://localhost:8501**.

### 5. Test Buy (optional)

Minimal UI to place a single contract (hardcoded or LLM-found market):

```bash
cd frontend
source ../treehacks2026/bin/activate
streamlit run test_buy.py
```

Opens on another port (e.g. 8502). Use **Buy 1 YES contract** to verify the Kalshi demo dashboard updates. Requires backend running.

---

Optional: replace tickers in `backend/themes.json` with real open Kalshi markets. Demo uses live tickers (Denver/Miami weather, Math & Logic).
