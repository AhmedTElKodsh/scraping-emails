"""Token-based authentication manager for app.farida.estate API.

Use this when you already have an authentication token from a browser session.
"""

import requests
import json
import os


class TokenAuthManager:
    """Handles authenticated requests using a pre-obtained token."""

    def __init__(self, contract_path=None, token=None):
        self.contract_path = contract_path or os.path.join(
            os.path.dirname(__file__), "..", "..", "data", "api_contract.json"
        )
        self.contract = self._load_contract()
        self.token = token or os.environ.get("FARIDA_TOKEN")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json",
            "Content-Type": "application/json",
        })
        
        if self.token:
            auth_config = self.contract.get("auth", {})
            token_header = auth_config.get("token_header", "Authorization")
            token_type = auth_config.get("token_type", "Bearer")
            self.session.headers[token_header] = f"{token_type} {self.token}"

    def _load_contract(self):
        with open(self.contract_path, "r") as f:
            contract = json.load(f)
        return contract

    @property
    def base_url(self):
        return self.contract["base_url"].rstrip("/")

    def login(self):
        """No-op for token-based auth - token is already set."""
        if not self.token:
            print("\n  ERROR: No token provided.")
            print("  Set FARIDA_TOKEN environment variable or pass token to constructor.")
            print("  You can get the token from your browser's DevTools after logging in.")
            raise ValueError("Token required for authentication")
        print(f"  Using pre-obtained authentication token.")

    def ensure_authenticated(self):
        """Ensure token is set."""
        if not self.token:
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
