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

### 6. Refresh themes (optional)

Pre-defined themes may use markets that have closed. To refresh `backend/themes.json` with current open markets:

```bash
cd backend
source ../treehacks2026/bin/activate
python scripts/update_themes.py
```

Restart the backend (uvicorn) to load the updated themes.

### 7. Initialize events database (required for search)

To search events by keyword and build baskets:

```bash
cd backend
source ../treehacks2026/bin/activate
python scripts/init_events_db.py
```

Creates `events.db` with events indexed by volume. The UI shows top 20 traded events by default; type a keyword to filter (e.g. Fed, NBA, Democratic).

### 8. Fetch events to file (optional)

To export the full events list for reference:

```bash
cd backend
python scripts/fetch_events.py
```

Creates:
- `events_list_summary.json` — slim reference — committed to repo
- `events_list.json` — full export — gitignored
