"""OTP-based authentication manager for app.farida.estate API."""

import requests
import json
import os
import time


class OTPAuthManager:
    """Handles OTP login for app.farida.estate with manual OTP input."""

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

    def send_otp(self, phone_number, country_code="+20", partner="y5l9he4a"):
        """Send OTP to phone number."""
        url = f"{self.base_url}/api/auth/otp/send"
        
        # Format: phone should be without country code, just the local number
        body = {
            "phone": str(phone_number),
            "countryCode": country_code,
            "partner": partner
        }
        
        print(f"  Sending OTP to {country_code}{phone_number}...")
        print(f"  Request body: {body}")  # Debug
        resp = self.session.post(url, json=body, timeout=30)
        
        if resp.status_code not in (200, 201):
            raise RuntimeError(
                f"OTP send failed with HTTP {resp.status_code}: {resp.text[:500]}"
            )
        
        print(f"  OTP sent successfully. Check your WhatsApp.")
        return resp.json()

    def verify_otp(self, phone_number, otp, country_code="+20"):
        """Verify OTP and obtain authentication token."""
        auth_config = self.contract["auth"]
        login_url = f"{self.base_url}{auth_config['login_endpoint']}"
        
        body = {
            "phone": phone_number,
            "countryCode": country_code,
            "otp": otp
        }
        
        print(f"  Verifying OTP...")
        resp = self.session.post(login_url, json=body, timeout=30)
        
        if resp.status_code not in (200, 201):
            raise RuntimeError(
                f"OTP verification failed with HTTP {resp.status_code}: {resp.text[:500]}"
            )
        
        self.token_obtained_at = time.time()
        
        # Extract token from response
        resp_data = resp.json()
        self.token = (
            resp_data.get("token")
            or resp_data.get("access_token")
            or resp_data.get("accessToken")
            or resp_data.get("data", {}).get("token")
            or resp_data.get("data", {}).get("access_token")
        )
        
        if self.token:
            token_header = auth_config.get("token_header", "Authorization")
            token_type = auth_config.get("token_type", "Bearer")
            self.session.headers[token_header] = f"{token_type} {self.token}"
            print(f"  Login successful. Token obtained.")
        else:
            print(f"  Login successful (cookie/session-based auth).")
        
        return resp_data

    def login(self, phone_number=None, country_code=None):
        """Interactive OTP login flow."""
        phone_number = phone_number or os.environ.get("FARIDA_EMAIL")
        country_code = country_code or os.environ.get("FARIDA_COUNTRY_CODE", "+20")
        
        if not phone_number:
            raise ValueError(
                "Phone number required. Set FARIDA_EMAIL environment variable "
                "or pass it directly."
            )
        
        # Clean phone number - keep the format as entered (with leading 0 if present)
        phone_clean = phone_number.lstrip("+")
        if phone_clean.startswith("20"):
            phone_clean = phone_clean[2:]
        # Don't strip leading 0 - API might expect it
        
        # Send OTP
        self.send_otp(phone_clean, country_code)
        
        # Get OTP from user
        otp = input("\n  Enter the OTP code you received: ").strip()
        
        # Verify OTP
        return self.verify_otp(phone_clean, otp, country_code)

    def is_token_expired(self):
        """Check if token needs refresh."""
        if not self.token_obtained_at:
            return True
        expiry = self.contract["auth"].get("token_expiry_seconds")
        if not expiry:
            return False
        elapsed = time.time() - self.token_obtained_at
        return elapsed >= (expiry - 60)

    def ensure_authenticated(self):
        """Login if needed."""
        if self.token is None and not self.session.cookies:
            self.login()
        elif self.is_token_expired():
            print("  Token expired, re-authenticating...")
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
