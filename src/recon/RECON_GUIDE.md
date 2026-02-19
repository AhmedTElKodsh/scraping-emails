# Layer 2 API Recon Guide — app.farida.estate

## Objective
Discover all API endpoints the SPA calls so we can replay them directly with Python `requests` (no browser needed after this step).

## Prerequisites
- Chrome browser with Claude extension enabled
- A registered user account on app.farida.estate
- Chrome DevTools (F12)

## Step-by-Step Recon Procedure

### Step 1 — Prepare Chrome DevTools
1. Open Chrome → navigate to `https://app.farida.estate`
2. Press **F12** to open DevTools
3. Go to the **Network** tab
4. Check **Preserve log** (so navigation doesn't clear entries)
5. Filter by **Fetch/XHR** (we only want API calls, not static assets)
6. Clear the current log (trash icon)

### Step 2 — Login Flow Capture
1. Navigate to `https://app.farida.estate/login`
2. Enter your credentials and submit
3. **WATCH the Network tab** — capture:
   - **Login endpoint URL** (e.g., `/api/auth/login`, `/api/v1/login`)
   - **Request method** (POST)
   - **Request headers** (especially `Content-Type`, any custom headers)
   - **Request body** (JSON shape: `{email, password}` or `{username, password}`)
   - **Response body** (look for JWT token, session cookie, refresh token)
   - **Response headers** (look for `Set-Cookie`, `Authorization`)

### Step 3 — Browse All Sections
After login, systematically visit every section of the app. For each page:
1. Click through the navigation/menu
2. Let the page fully load
3. Note which API calls fire in the Network tab

**Pages to visit (likely structure):**
- Dashboard / Home
- Projects / Properties listing
- Individual project/property detail pages (click into several)
- Investment opportunities
- Portfolio / My Investments
- Profile / Account settings
- Any "Explore" or "Browse" sections

### Step 4 — Document Each API Endpoint

For each unique API call you see, record:

```json
{
  "endpoint": "/api/projects",
  "method": "GET",
  "auth_header": "Bearer eyJ...",
  "query_params": {"page": 1, "limit": 20},
  "request_body": null,
  "response_status": 200,
  "response_sample": "paste first few lines of response JSON",
  "pagination": "cursor-based / offset / page-number",
  "notes": "returns list of investment projects"
}
```

### Step 5 — Export Data

**Option A — Manual JSON file:**
Save your findings to `data/api_contract.json` using this template:

```json
{
  "base_url": "https://app.farida.estate",
  "auth": {
    "login_endpoint": "/api/auth/login",
    "method": "POST",
    "body_shape": {"email": "string", "password": "string"},
    "token_type": "Bearer JWT | Session Cookie",
    "token_location": "header:Authorization | cookie:session_id",
    "token_expiry": "unknown — check response",
    "refresh_endpoint": "/api/auth/refresh (if exists)"
  },
  "endpoints": [
    {
      "name": "list_projects",
      "url": "/api/projects",
      "method": "GET",
      "auth_required": true,
      "pagination": {"type": "page", "params": ["page", "limit"]},
      "response_shape": "describe the JSON structure",
      "sample_response": {}
    }
  ]
}
```

**Option B — HAR file export:**
1. In DevTools Network tab, right-click → **Save all as HAR with content**
2. Save as `data/recon_capture.har`
3. We can parse this programmatically later

### Step 6 — Key Things to Watch For

| Signal | What to look for |
|--------|-----------------|
| **Auth mechanism** | JWT in `Authorization` header vs. session cookie |
| **Token refresh** | Does the app call a `/refresh` endpoint periodically? |
| **API versioning** | `/api/v1/` vs `/api/` vs `/graphql` |
| **Pagination** | Page-based, cursor-based, or offset-based |
| **Rate limit headers** | `X-RateLimit-*`, `Retry-After` |
| **WebSocket** | Check WS tab — does the app use real-time connections? |
| **GraphQL** | Single `/graphql` endpoint with varying `query` bodies |
| **CSRF tokens** | Hidden tokens in forms or `X-CSRF-Token` headers |

### Step 7 — Claude Extension Usage

Use the Claude extension to help document findings in real-time:
- Ask Claude to summarize the API contract from your screenshots
- Have Claude identify patterns in the request/response shapes
- Use Claude to generate the `api_contract.json` from your notes

## After Recon

Once `data/api_contract.json` is populated, we'll build `src/scrapers/app_scraper.py` to:
1. Authenticate via the discovered login endpoint
2. Fetch all discovered data endpoints
3. Store everything in the same SQLite database
4. Handle token refresh automatically
