# Kalshi ETF Engine

A thematic ETF engine for Kalshi event contracts.

## Setup

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Environment Configuration**:
   - Rename `.env.example` to `.env`.
   - Add your Kalshi API Key ID and path to your private key.
   - Add your OpenAI API Key.

   ```
   KALSHI_API_KEY_ID=...
   KALSHI_PRIVATE_KEY_PATH=/path/to/private_key.pem
   OPENAI_API_KEY=...
   ```

## Usage

1. **Run the Application**:
   ```bash
   streamlit run main.py
   ```

2. **Interface**:
   - Enter a **Trend Thesis** (e.g., "AI Stall", "Inflation Rising").
   - Set your **Budget**.
   - Click **Generate ETF** to see AI-selected contracts.
   - Click **Execute Trade** to submit atomic batch orders to Kalshi.

## Architecture

- **Auth**: RSA-PSS Signing via `cryptography`.
- **Discovery**: Fetches events from Kalshi, uses GPT-4o-mini to select tickers.
- **Execution**: Batched orders via Kalshi v2 API.