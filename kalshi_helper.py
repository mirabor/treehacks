import os
import time
import base64
import json
import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"

class KalshiClient:
    def __init__(self):
        self.key_id = os.getenv("KALSHI_API_KEY_ID")
        private_key_input = os.getenv("KALSHI_PRIVATE_KEY_PATH")
        
        if not self.key_id or not private_key_input:
            raise ValueError("Missing KALSHI_API_KEY_ID or KALSHI_PRIVATE_KEY_PATH in .env")

        # Check if the input is a file path
        if os.path.exists("private_key.pem"):
            with open("private_key.pem", "rb") as key_file:
                key_data = key_file.read()
            # If we found the file, we can optionally update the valid path for reference, but key_data is set.
        elif os.path.exists(private_key_input):
            with open(private_key_input, "rb") as key_file:
                key_data = key_file.read()
        else:
            # Assume it is the key content directly
            # Clean up the input first
            private_key_input = private_key_input.strip()
            
            if "-----BEGIN" not in private_key_input:
                # Basic heuristic for RSA/PKCS8 keys
                # Remove any spaces/newlines from the base64 string just in case
                clean_key = "".join(private_key_input.split())
                # Ensure we have a valid base64 length (padding) if possible, but python's b64decode might handle it?
                # Actually, cryptography requires strict PEM. 
                # Let's break the clean key into 64-char lines to be safe conformant PEM
                chunked_key = '\n'.join([clean_key[i:i+64] for i in range(0, len(clean_key), 64)])
                formatted_key = f"-----BEGIN PRIVATE KEY-----\n{chunked_key}\n-----END PRIVATE KEY-----"
                key_data = formatted_key.encode('utf-8')
            else:
                # If it has headers, ensure newlines are respected
                if "\\n" in private_key_input:
                     private_key_input = private_key_input.replace("\\n", "\n")
                
                # Check if the middle content is one huge line, which some parsers hate.
                # If so, we might need to reformat it. 
                # But typically cryptography lib is okay if headers are on own lines.
                if "\n" not in private_key_input.strip()[27:-25]: # simplified check
                     # It might be mashed. 
                     # This is risky to regex without damaging headers. 
                     # Let's trust the user or the simple replacement first.
                     pass

                key_data = private_key_input.encode('utf-8')

        try:
            self.private_key = serialization.load_pem_private_key(
                key_data,
                password=None
            )
        except Exception as e:
            # Re-raise with a clear message, but also print the first/last few chars to help debug
            preview = key_data.decode('utf-8')[:30] + "..." + key_data.decode('utf-8')[-30:] if len(key_data) > 60 else key_data.decode('utf-8')
            raise ValueError(f"Failed to load private key. Ensure it is a valid path or PEM string. Error: {e}. Key Preview: {preview}")

    def sign_request(self, method, path, timestamp):
        msg = f"{timestamp}{method}{path}".encode('utf-8')
        signature = self.private_key.sign(
            msg,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return base64.b64encode(signature).decode('utf-8')

    def _make_request(self, method, endpoint, params=None, data=None):
        path = f"/trade-api/v2{endpoint}"
        timestamp = str(int(time.time() * 1000))
        signature = self.sign_request(method, path, timestamp)

        headers = {
            "KALSHI-API-KEY": self.key_id,
            "KALSHI-API-SIGNATURE": signature,
            "KALSHI-API-TIMESTAMP": timestamp,
            "Content-Type": "application/json"
        }
        
        url = f"{BASE_URL}{endpoint}"
        
        try:
            if method == "GET":
                response = requests.get(url, headers=headers, params=params)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=data)
            else:
                return {"error": f"Unsupported method: {method}"}

            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            try:
                error_data = e.response.json()
                return {"error": f"API Error: {error_data}"}
            except:
                return {"error": f"HTTP Error: {str(e)}"}
        except Exception as e:
            return {"error": f"Request Failed: {str(e)}"}

    def get_open_events(self, limit=100):
        """Fetch open events from Kalshi."""
        # fetching events that are open and active
        params = {
            "status": "open",
            "limit": limit
        }
        params_str = "&".join([f"{k}={v}" for k, v in params.items()])
        # Note: Signing usually requires the full path including query params if strictly implemented,
        # but Kalshi v2 docs say sign method+path. 
        # For simplicity and standard v2, usually path implies the route. 
        # Let's verify if query params are needed in signature. 
        # Documentation says: "The path is the part of the URL after the domain, including the query string."
        # IMPORTANT: We need to include query params in the path for signature if they exist.
        
        endpoint = "/events"
        full_path_for_sign = f"/trade-api/v2{endpoint}"
        if params:
             full_path_for_sign += "?" + params_str

        # Re-implement _make_request logic slightly for GET with params to ensure signature correctness
        timestamp = str(int(time.time() * 1000))
        msg = f"{timestamp}GET{full_path_for_sign}".encode('utf-8')
        signature = self.private_key.sign(
            msg,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        b64_signature = base64.b64encode(signature).decode('utf-8')
        
        headers = {
            "KALSHI-API-KEY": self.key_id,
            "KALSHI-API-SIGNATURE": b64_signature,
            "KALSHI-API-TIMESTAMP": timestamp,
            "Content-Type": "application/json"
        }

        url = f"{BASE_URL}{endpoint}"
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            return response.json()
        else:
             return {"error": response.text}

    def submit_batch_orders(self, orders):
        """
        Submit a batch of orders.
        orders: list of dicts with 'ticker', 'action', 'count', 'client_order_id', 'side', 'type'
        API Endpoint: POST /portfolio/orders/batched
        """
        # orders structure expected by Kalshi:
        # { "orders": [ { "action": "buy", "count": 1, "side": "yes", "ticker": "...", "type": "market", "client_order_id": "..." } ] }
        
        payload = {"orders": orders}
        return self._make_request("POST", "/portfolio/orders/batched", data=payload)
