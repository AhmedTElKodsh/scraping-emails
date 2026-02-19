# Implementation Plan: Farida Estate Recurring Scraping Pipeline

## Project Overview

**Purpose:** Market research & data aggregation from farida.estate (public WordPress site) and app.farida.estate (authenticated investment SPA).

**Architecture:** Two-layer scraping pipeline with shared SQLite storage, scheduled execution, and monitoring.

---

## Current Status (Completed)

| Item                                  | Status                                                                       |
| ------------------------------------- | ---------------------------------------------------------------------------- |
| Layer 1 one-shot WordPress scraper    | DONE — 64 items extracted (4 posts, 7 pages, 48 media, 4 categories, 1 user) |
| SQLite database with upsert logic     | DONE — `data/farida.db`                                                      |
| Scrape run logging                    | DONE — `scrape_runs` table                                                   |
| Layer 2 auth manager                  | DONE — token-based + cookie-based auth support                               |
| Layer 2 app scraper (contract-driven) | DONE — reads `api_contract.json`, dynamic table creation                     |
| API recon guide for Chrome DevTools   | DONE — `src/recon/RECON_GUIDE.md`                                            |

---

## Phase 1: Layer 2 API Discovery ✅ COMPLETED

**What:** Use Chrome + DevTools + MCP Playwright to discover app.farida.estate's API contract.

**Steps:**

1. ✅ Create user account on app.farida.estate
2. ✅ Automated browser navigation and authentication via MCP Playwright
3. ✅ Populate `data/api_contract.json` with discovered endpoints
4. ✅ Create `.env` with credentials template

**Deliverable:** Completed `api_contract.json` with auth config + all discovered endpoints.

**Status:** COMPLETED - Discovered 12 API endpoints across authentication, wallet, properties, portfolio, and investor profile domains.

---

## Phase 2: Layer 2 One-Shot Extraction ✅ COMPLETED

**What:** Run `src/scrapers/app_scraper.py` against populated contract.

**Steps:**

1. ✅ Verify `.env` credentials are set
2. ✅ Run `python src/scrapers/app_scraper.py`
3. ✅ Validate extracted data in SQLite
4. ✅ Adjust scraper if API responses have unexpected shapes

**Depends on:** Phase 1 complete.

**Status:** COMPLETED - Successfully extracted data from all 10 API endpoints (profile_status, wallet_balance, investor_preferences, investor_profile, properties_for_you, assets_amounts, properties, portfolio, wallet_due_amount, wallet_transactions). All data stored in SQLite with 0 errors. Token-based authentication working perfectly.

---

## Phase 3: Recurring Scheduler ✅ COMPLETED

**What:** Add scheduled execution for both layers on configurable intervals.

### Epic 3.1 — Configuration System ✅

- **Story:** Create `config.yaml` for scrape intervals, endpoint toggles, retry settings
- **AC:** Config file controls Layer 1 interval (e.g., daily), Layer 2 interval (e.g., every 6 hours), max retries, request delay
- **Status:** COMPLETED - `config.yaml` created with all configuration options

### Epic 3.2 — Scheduler Module ✅

- **Story:** Implement `src/scheduler/scheduler.py` using `schedule` library
- **AC:** Both scrapers run on configured intervals, logs each run, survives errors without crashing
- **Tasks:**
  1. ✅ Add `schedule` to requirements.txt
  2. ✅ Create scheduler that reads config.yaml
  3. ✅ Register Layer 1 and Layer 2 scrape jobs
  4. ✅ Add graceful shutdown (SIGINT/SIGTERM handling)
  5. ✅ Add `main.py` entry point that starts scheduler
- **Status:** COMPLETED - Scheduler fully functional with multiple execution modes

### Epic 3.3 — Retry & Error Handling

- **Story:** Add exponential backoff retry on failed requests, circuit breaker for repeated failures
- **AC:** Retries up to 3x with backoff, stops scraping endpoint after 5 consecutive failures, logs all errors
- **Status:** DEFERRED - Basic error handling in place, advanced retry logic to be added in Phase 4

**Overall Status:** COMPLETED - Scheduler operational with config system, graceful shutdown, and logging. See `docs/SCHEDULER_GUIDE.md` for usage.

---

## Phase 4: Data Quality & Monitoring

### Epic 4.1 — Deduplication & Change Detection

- **Story:** Track data changes between scrape runs
- **AC:** Upserts update existing rows (already implemented), new `data_changes` table logs what changed per run
- **Tasks:**
  1. Add `data_changes` table (item_id, field, old_value, new_value, detected_at)
  2. Compare before/after on upsert for Layer 2 data
  3. Summary report of changes per run

### Epic 4.2 — Health Monitoring

- **Story:** Create `src/monitoring/health.py` that checks scrape health
- **AC:** Alerts if: last successful scrape > 2x interval, error rate > 50%, zero items scraped
- **Tasks:**
  1. Query `scrape_runs` table for health metrics
  2. Console output / log file with health status
  3. Optional: webhook notification (Slack/Discord/email)

### Epic 4.3 — Schema Drift Detection

- **Story:** Detect when API response shapes change
- **AC:** Compare response keys against expected schema, log warnings on new/missing fields
- **Tasks:**
  1. Store expected response schema in contract
  2. Validate each response against schema
  3. Log drift events to `schema_drift` table

---

## Phase 5: Data Export & Analysis

### Epic 5.1 — Export Utilities

- **Story:** Export scraped data to CSV/JSON for analysis
- **Tasks:**
  1. `src/export/csv_export.py` — export any table to CSV
  2. `src/export/json_export.py` — export any table to JSON
  3. CLI interface: `python -m src.export --table wp_posts --format csv`

### Epic 5.2 — Data Analysis Queries

- **Story:** Pre-built SQL queries for market research insights
- **Tasks:**
  1. Investment project trends over time
  2. Price/yield comparisons
  3. New listings detection
  4. Content publishing frequency

---

## Project Structure (Target)

```
AI-Scraping/
├── src/
│   ├── scrapers/
│   │   ├── wp_scraper.py        ✅ Done
│   │   └── app_scraper.py       ✅ Done
│   ├── auth/
│   │   ├── token_auth_manager.py ✅ Done
│   │   └── otp_auth_manager.py   ✅ Done
│   ├── recon/
│   │   └── RECON_GUIDE.md       ✅ Done
│   ├── storage/
│   │   └── database.py          ✅ Done
│   ├── scheduler/
│   │   └── scheduler.py         ✅ Done
│   ├── monitoring/
│   │   └── health.py            Phase 4
│   └── export/
│       ├── csv_export.py        Phase 5
│       └── json_export.py       Phase 5
├── data/
│   ├── farida.db                ✅ Done (64 WP items + 10 app tables)
│   └── api_contract.json        ✅ Done (10 endpoints)
├── docs/
│   └── SCHEDULER_GUIDE.md       ✅ Done
├── logs/
│   └── scraper.log              ✅ Auto-created
├── config.yaml                  ✅ Done
├── main.py                      ✅ Done
├── .env                         ✅ Done (with token)
├── .env.example                 ✅ Done
├── .gitignore                   ✅ Done
└── requirements.txt             ✅ Done
```

---

## Priority Order

| Priority  | Phase                        | Blocked On   |
| --------- | ---------------------------- | ------------ |
| **DONE**  | Phase 1 — API Recon          | ✅ Completed |
| **DONE**  | Phase 2 — Layer 2 extraction | ✅ Completed |
| **DONE**  | Phase 3 — Scheduler          | ✅ Completed |
| **NOW**   | Phase 4 — Monitoring         | Ready        |
| **Later** | Phase 5 — Export & Analysis  | Data flowing |

---

## Tech Stack

| Component   | Choice       | Rationale                                                   |
| ----------- | ------------ | ----------------------------------------------------------- |
| HTTP client | `requests`   | Simple, proven, no async needed for our scale               |
| Storage     | SQLite (WAL) | Portable, queryable, zero-config, sufficient for our volume |
| Scheduler   | `schedule`   | Lightweight, in-process, no external deps                   |
| Auth        | Token-based  | Pre-obtained JWT from browser, handles expiry               |
| Config      | YAML         | Human-readable, structured                                  |
| Logging     | stdlib       | Built-in, file + console output                             |
| Export      | stdlib       | `csv` + `json` modules, no external deps needed             |
