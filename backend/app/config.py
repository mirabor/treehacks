"""Load config from environment."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Kalshi API (use demo for testing: https://demo-api.kalshi.co)
KALSHI_BASE_URL: str = os.getenv("KALSHI_BASE_URL", "https://demo-api.kalshi.co")
KALSHI_API_KEY_ID: str = os.getenv("KALSHI_API_KEY_ID", "")
KALSHI_PRIVATE_KEY_PATH: str = os.getenv(
    "KALSHI_PRIVATE_KEY_PATH",
    str(Path(__file__).resolve().parent.parent / "kalshi_private.key"),
)
# Optional: inline PEM instead of file (e.g. in CI)
KALSHI_PRIVATE_KEY_PEM: str = os.getenv("KALSHI_PRIVATE_KEY_PEM", "")

# Backend URL for Streamlit (default same host)
BACKEND_URL: str = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

# OpenAI (for LLM basket generation)
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
