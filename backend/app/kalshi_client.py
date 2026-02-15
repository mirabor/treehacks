"""Kalshi API client with RSA-PSS request signing."""
import base64
import time
from typing import Any

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from app.config import (
    KALSHI_BASE_URL,
    KALSHI_API_KEY_ID,
    KALSHI_PRIVATE_KEY_PATH,
    KALSHI_PRIVATE_KEY_PEM,
)


def _load_private_key():
    if KALSHI_PRIVATE_KEY_PEM:
        pem = KALSHI_PRIVATE_KEY_PEM.replace("\\n", "\n")
        return serialization.load_pem_private_key(
            pem.encode(),
            password=None,
        )
    path = KALSHI_PRIVATE_KEY_PATH
    with open(path, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)


def _sign(timestamp: str, method: str, path: str, private_key) -> str:
    path_only = path.split("?")[0]
    message = f"{timestamp}{method}{path_only}".encode("utf-8")
    signature = private_key.sign(
        message,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH,
        ),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode("utf-8")


def _headers(method: str, path: str, private_key) -> dict[str, str]:
    timestamp = str(int(time.time() * 1000))
    sig = _sign(timestamp, method, path, private_key)
    return {
        "KALSHI-ACCESS-KEY": KALSHI_API_KEY_ID,
        "KALSHI-ACCESS-TIMESTAMP": timestamp,
        "KALSHI-ACCESS-SIGNATURE": sig,
        "Content-Type": "application/json",
    }


class KalshiClient:
    """Minimal Kalshi API client: markets (public) and batched orders (auth)."""

    def __init__(self):
        self.base = KALSHI_BASE_URL.rstrip("/")
        self._key = None

    def _get_key(self):
        if self._key is None and (KALSHI_API_KEY_ID and (KALSHI_PRIVATE_KEY_PEM or KALSHI_PRIVATE_KEY_PATH)):
            self._key = _load_private_key()
        return self._key

    def get_markets(self, tickers: list[str]) -> dict[str, Any]:
        """Fetch market snapshots by ticker. Returns dict ticker -> market object."""
        if not tickers:
            return {}
        path = "/trade-api/v2/markets"
        params = {"tickers": ",".join(tickers)}
        with httpx.Client() as client:
            r = client.get(f"{self.base}{path}", params=params, timeout=15.0)
            r.raise_for_status()
            data = r.json()
        out = {}
        for m in data.get("markets", []):
            out[m["ticker"]] = m
        return out

    def get_open_markets(self, limit: int = 300) -> list[dict]:
        """Fetch open markets (public, no auth). Returns list of market objects."""
        path = "/trade-api/v2/markets"
        params = {"status": "open", "limit": min(limit, 1000)}
        all_markets = []
        with httpx.Client() as client:
            while True:
                r = client.get(f"{self.base}{path}", params=params, timeout=30.0)
                r.raise_for_status()
                data = r.json()
                markets = data.get("markets", [])
                all_markets.extend(markets)
                cursor = data.get("cursor")
                if not cursor or len(markets) == 0 or len(all_markets) >= limit:
                    break
                params = {"status": "open", "limit": params["limit"], "cursor": cursor}
        return all_markets[:limit]

    def batch_create_orders(self, orders: list[dict]) -> dict[str, Any]:
        """POST /portfolio/orders/batched. orders: list of CreateOrderRequest."""
        key = self._get_key()
        if not key:
            raise RuntimeError("Kalshi API key not configured")
        path = "/trade-api/v2/portfolio/orders/batched"
        body = {"orders": orders}
        h = _headers("POST", path, key)
        with httpx.Client() as client:
            r = client.post(
                f"{self.base}{path}",
                json=body,
                headers=h,
                timeout=15.0,
            )
            if r.status_code >= 400:
                try:
                    err = r.json()
                    e = err.get("error") if isinstance(err.get("error"), dict) else {}
                    msg = e.get("message") or err.get("message") or r.text or f"HTTP {r.status_code}"
                except Exception:
                    msg = r.text or f"HTTP {r.status_code}"
                raise httpx.HTTPStatusError(msg, request=r.request, response=r)
            return r.json()
