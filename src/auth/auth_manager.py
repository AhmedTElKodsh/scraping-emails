"""Authentication manager for app.farida.estate API."""

import requests
import json
import os
import time
from datetime import datetime, timezone


class AuthManager:
    """Handles login, token storage, and refresh for app.farida.estate."""

    def __init__(self, contract_path=None):
        self.contract_path = contract_path or os.path.join(
            os.path.dirname(__file__), "..", "..", "data", "api_contract.json"
        )
        self.contract = self._load_contract()
        self.token = None
        self.token_obtained_at = None
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json",
            "Content-Type": "application/json",
        })

    def _load_contract(self):
        with open(self.contract_path, "r") as f:
            contract = json.load(f)
        if not contract.get("auth", {}).get("login_endpoint"):
            raise ValueError(
                "API contract is not configured. "
                "Run the Chrome DevTools recon first (see src/recon/RECON_GUIDE.md)"
            )
        return contract

    @property
    def base_url(self):
        return self.contract["base_url"].rstrip("/")

    def login(self, email=None, password=None):
        """Authenticate and store the token."""
        email = email or os.environ.get("FARIDA_EMAIL")
        password = password or os.environ.get("FARIDA_PASSWORD")

        if not email or not password:
            raise ValueError(
                "Credentials required. Set FARIDA_EMAIL and FARIDA_PASSWORD "
                "environment variables or pass them directly."
            )

        auth_config = self.contract["auth"]
        login_url = f"{self.base_url}{auth_config['login_endpoint']}"

        # Build request body from contract shape
        body = dict(auth_config.get("body_shape", {}))
        # Replace placeholder values with actual credentials
        for key in body:
            if "email" in key.lower() or "username" in key.lower():
                body[key] = email
            elif "password" in key.lower():
                body[key] = password

        # If body_shape is empty, use standard email/password
        if not body:
            body = {"email": email, "password": password}

        print(f"  Logging in to {login_url}...")
        resp = self.session.request(
            method=auth_config.get("method", "POST"),
            url=login_url,
            json=body,
            timeout=30,
        )

        if resp.status_code not in (200, 201):
            raise RuntimeError(
                f"Login failed with HTTP {resp.status_code}: {resp.text[:500]}"
            )

        self.token_obtained_at = time.time()

        # Extract token based on contract config
        token_header = auth_config.get("token_header", "Authorization")
        token_type = auth_config.get("token_type", "Bearer")

        resp_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}

        # Try common token locations in response
        self.token = (
            resp_data.get("token")
            or resp_data.get("access_token")
            or resp_data.get("accessToken")
            or resp_data.get("data", {}).get("token")
            or resp_data.get("data", {}).get("access_token")
        )

        if self.token:
            self.session.headers[token_header] = f"{token_type} {self.token}"
            print(f"  Login successful. Token obtained.")
        else:
            # Maybe auth is cookie-based — session cookies are auto-stored
            print(f"  Login successful (cookie/session-based auth).")

        return resp_data

    def is_token_expired(self):
        """Check if token needs refresh based on contract expiry config."""
        if not self.token_obtained_at:
            return True
        expiry = self.contract["auth"].get("token_expiry_seconds")
        if not expiry:
            return False  # Unknown expiry, assume valid
        elapsed = time.time() - self.token_obtained_at
        return elapsed >= (expiry - 60)  # Refresh 60s before expiry

    def ensure_authenticated(self):
        """Login or refresh if needed."""
        if self.token is None and not self.session.cookies:
            self.login()
        elif self.is_token_expired():
            refresh_ep = self.contract["auth"].get("refresh_endpoint")
            if refresh_ep:
                self._refresh_token(refresh_ep)
            else:
                self.login()  # Re-login if no refresh endpoint

    def _refresh_token(self, refresh_endpoint):
        """Attempt token refresh."""
        url = f"{self.base_url}{refresh_endpoint}"
        print(f"  Refreshing token via {url}...")
        resp = self.session.post(url, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            new_token = data.get("token") or data.get("access_token")
            if new_token:
                self.token = new_token
                self.token_obtained_at = time.time()
                token_header = self.contract["auth"].get("token_header", "Authorization")
                token_type = self.contract["auth"].get("token_type", "Bearer")
                self.session.headers[token_header] = f"{token_type} {self.token}"
                print("  Token refreshed.")
                return
        # Refresh failed, re-login
        print("  Refresh failed, re-logging in...")
        self.login()

    def get(self, endpoint, params=None):
        """Authenticated GET request."""
        self.ensure_authenticated()
        url = f"{self.base_url}{endpoint}"
        return self.session.get(url, params=params, timeout=30)

    def post(self, endpoint, json_body=None):
        """Authenticated POST request."""
        self.ensure_authenticated()
        url = f"{self.base_url}{endpoint}"
        return self.session.post(url, json=json_body, timeout=30)
