"""Scraping-Emails — Streamlit Dashboard.

A free, stealth web scraping engine for B2B lead extraction from
Clutch.co and Sortlist.com with automatic email discovery.
"""

import logging
import os
import time
import threading
import queue

import pandas as pd
import streamlit as st

from config.categories import get_category_url, get_categories
from scrapers.clutch import ClutchScraper
from scrapers.sortlist import SortlistScraper
from extractors.email_extractor import EmailExtractor
from utils.export import to_csv, to_excel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Page config
st.set_page_config(
    page_title="Scraping-Emails",
    page_icon="📧",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Thread-safe shared state ────────────────────────────────────────
# Use a queue so the background thread can push results without touching
# st.session_state (which is NOT thread-safe for writes).

if "result_queue" not in st.session_state:
    st.session_state.result_queue = queue.Queue()

if "log_queue" not in st.session_state:
    st.session_state.log_queue = queue.Queue()


def init_session_state():
    """Initialize session state variables."""
    defaults = {
        "rows": [],           # list of dicts (thread-safe via queue drain)
        "scraping": False,
        "completed": False,
        "stop_event": threading.Event(),
        "total_scraped": 0,
        "total_emails_found": 0,
        "log_messages": [],
        "scraper_thread": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def drain_queues():
    """Pull all pending results and log messages from the background thread.

    This is the ONLY place we mutate session_state with data from the thread.
    Called once per Streamlit rerun on the main thread.
    """
    changed = False

    # Drain results
    while True:
        try:
            row = st.session_state.result_queue.get_nowait()
        except queue.Empty:
            break
        st.session_state.rows.append(row)
        st.session_state.total_scraped += 1
        if row.get("email") and row["email"] != "Unreachable":
            st.session_state.total_emails_found += 1
        changed = True

    # Drain log messages
    while True:
        try:
            msg = st.session_state.log_queue.get_nowait()
        except queue.Empty:
            break
        st.session_state.log_messages.append(msg)
        if len(st.session_state.log_messages) > 200:
            st.session_state.log_messages = st.session_state.log_messages[-200:]
        changed = True

    return changed


def _log(msg: str, log_q: queue.Queue):
    """Thread-safe logging: push to queue + Python logger."""
    timestamp = time.strftime("%H:%M:%S")
    log_q.put(f"[{timestamp}] {msg}")
    logger.info(msg)


def get_scraper(site: str, headless: bool | str = True, proxy_server: str = ""):
    """Create the appropriate scraper for the given site."""
    if site == "Clutch.co":
        return ClutchScraper(headless=headless, proxy_server=proxy_server)
    elif site == "Sortlist.com":
        return SortlistScraper(headless=headless, proxy_server=proxy_server)
    else:
        raise ValueError(f"Unknown site: {site}")


def run_scraper_thread(
    tasks: list[tuple[str, str, str]],
    result_q: queue.Queue,
    log_q: queue.Queue,
    stop_event: threading.Event,
    proxy_server: str = "",
):
    """Run scraping in a background thread.

    Pushes each company dict into result_q as soon as it's ready.
    The main thread drains the queue on every rerun to update the UI.
    """
    for site, category, url in tasks:
        if stop_event.is_set():
            break

        scraper = get_scraper(site, proxy_server=proxy_server)
        try:
            _log(f"Starting {site} scraper for {category}...", log_q)
            if proxy_server:
                _log(f"  Using proxy: {proxy_server.split('@')[-1]}", log_q)
            scraper.start_browser()
            email_extractor = EmailExtractor(scraper.page)
            _log(f"Navigating to {url}", log_q)

            company_count = 0
            for company in scraper.scrape_category(url):
                if stop_event.is_set():
                    _log("Stop requested by user. Finishing...", log_q)
                    break

                company_count += 1
                _log(f"[{company_count}] Scraped: {company.get('name', 'Unknown')}", log_q)

                # Extract email
                website_url = company.get("website_url", "")
                if website_url:
                    _log(f"  Extracting email from {website_url[:60]}...", log_q)
                    try:
                        email = email_extractor.find_email(website_url)
                    except Exception as e:
                        logger.warning("Email extraction error: %s", e)
                        email = "Unreachable"
                    company["email"] = email
                    if email != "Unreachable":
                        _log(f"  Email found: {email}", log_q)
                    else:
                        _log(f"  No email found", log_q)
                else:
                    company["email"] = "Unreachable"
                    _log(f"  No website URL — skipping email extraction", log_q)

                # Push completed row into queue immediately
                result_q.put(company)

            # Diagnose empty results
            if company_count == 0:
                _log(f"WARNING: 0 companies found on {site}!", log_q)
                # Capture page title and snippet for debugging
                try:
                    title = scraper.page.title()
                    _log(f"  Page title: {title}", log_q)
                    # Check for Cloudflare / bot detection
                    content = scraper.page.content()[:2000]
                    if "cloudflare" in content.lower() or "cf-browser-verification" in content.lower():
                        _log(f"  BLOCKED: Cloudflare anti-bot page detected!", log_q)
                    elif "captcha" in content.lower() or "recaptcha" in content.lower():
                        _log(f"  BLOCKED: CAPTCHA detected!", log_q)
                    elif "access denied" in content.lower() or "403" in content.lower():
                        _log(f"  BLOCKED: Access denied (403)!", log_q)
                    else:
                        # Log a snippet of the page to help debug selector issues
                        text = scraper.page.inner_text("body")[:500]
                        _log(f"  Page text preview: {text[:300]}", log_q)
                except Exception as diag_err:
                    _log(f"  Could not diagnose page: {diag_err}", log_q)

            _log(f"Finished {site}/{category}: {company_count} companies scraped.", log_q)

        except Exception as e:
            _log(f"Error during {site} scraping: {e}", log_q)
            logger.exception("Scraping error for %s", site)

        finally:
            scraper.close_browser()

    _log("All scraping tasks complete.", log_q)


def main():
    """Main Streamlit application."""
    init_session_state()

    # ── Drain queues on every rerun ──────────────────────────────────
    drain_queues()

    # Check if background thread finished
    thread = st.session_state.scraper_thread
    if thread is not None and not thread.is_alive():
        # Final drain to pick up any remaining items
        drain_queues()
        st.session_state.scraping = False
        st.session_state.completed = True
        st.session_state.scraper_thread = None

    # ── Header ───────────────────────────────────────────────────────
    st.title("📧 Scraping-Emails")
    st.markdown(
        "**Free B2B lead extraction** from Clutch.co & Sortlist.com with automatic email discovery."
    )

    # ── Sidebar — Configuration ──────────────────────────────────────
    with st.sidebar:
        st.header("Configuration")

        site_option = st.radio(
            "Select Site",
            options=["Clutch.co", "Sortlist.com", "Both"],
            index=0,
            disabled=st.session_state.scraping,
        )

        selected_tasks = []
        if site_option == "Both":
            st.subheader("Clutch.co Category")
            clutch_category = st.selectbox(
                "Clutch Category",
                options=get_categories("Clutch.co"),
                key="clutch_cat",
                disabled=st.session_state.scraping,
            )
            st.subheader("Sortlist.com Category")
            sortlist_category = st.selectbox(
                "Sortlist Category",
                options=get_categories("Sortlist.com"),
                key="sortlist_cat",
                disabled=st.session_state.scraping,
            )
            selected_tasks = [
                ("Clutch.co", clutch_category, get_category_url("Clutch.co", clutch_category)),
                ("Sortlist.com", sortlist_category, get_category_url("Sortlist.com", sortlist_category)),
            ]
        else:
            category = st.selectbox(
                f"{site_option} Category",
                options=get_categories(site_option),
                disabled=st.session_state.scraping,
            )
            selected_tasks = [
                (site_option, category, get_category_url(site_option, category)),
            ]

        st.divider()

        # Proxy configuration (needed for cloud hosting to bypass Cloudflare)
        with st.expander("Proxy Settings (Advanced)"):
            st.caption(
                "Clutch.co blocks datacenter IPs. To scrape from cloud hosting, "
                "provide a residential/rotating proxy."
            )
            proxy_server = st.text_input(
                "Proxy URL",
                value=os.environ.get("PROXY_SERVER", ""),
                placeholder="http://user:pass@host:port",
                type="password",
                disabled=st.session_state.scraping,
                key="proxy_input",
            )

        st.divider()

        # Start / Stop buttons
        col1, col2 = st.columns(2)
        with col1:
            start_clicked = st.button(
                "Start Scraping",
                type="primary",
                disabled=st.session_state.scraping,
                use_container_width=True,
            )
        with col2:
            stop_clicked = st.button(
                "Stop",
                disabled=not st.session_state.scraping,
                use_container_width=True,
            )

        if stop_clicked:
            st.session_state.stop_event.set()

        # Reset button (shown after completion)
        if st.session_state.completed:
            if st.button("New Scrape", use_container_width=True):
                st.session_state.rows = []
                st.session_state.scraping = False
                st.session_state.completed = False
                st.session_state.stop_event = threading.Event()
                st.session_state.total_scraped = 0
                st.session_state.total_emails_found = 0
                st.session_state.log_messages = []
                st.session_state.scraper_thread = None
                # Clear queues
                st.session_state.result_queue = queue.Queue()
                st.session_state.log_queue = queue.Queue()
                st.rerun()

        st.divider()

        # Stats
        st.subheader("Stats")
        st.metric("Companies Scraped", st.session_state.total_scraped)
        st.metric("Emails Found", st.session_state.total_emails_found)
        if st.session_state.total_scraped > 0:
            rate = (st.session_state.total_emails_found / st.session_state.total_scraped) * 100
            st.metric("Email Hit Rate", f"{rate:.1f}%")

    # ── Start scraping ───────────────────────────────────────────────
    if start_clicked and not st.session_state.scraping:
        st.session_state.rows = []
        st.session_state.scraping = True
        st.session_state.completed = False
        st.session_state.stop_event = threading.Event()
        st.session_state.total_scraped = 0
        st.session_state.total_emails_found = 0
        st.session_state.log_messages = []
        st.session_state.result_queue = queue.Queue()
        st.session_state.log_queue = queue.Queue()

        thread = threading.Thread(
            target=run_scraper_thread,
            args=(
                selected_tasks,
                st.session_state.result_queue,
                st.session_state.log_queue,
                st.session_state.stop_event,
                proxy_server,
            ),
            daemon=True,
        )
        st.session_state.scraper_thread = thread
        thread.start()
        st.rerun()

    # ── Progress indicator ───────────────────────────────────────────
    if st.session_state.scraping:
        st.info(f"Scraping in progress... {st.session_state.total_scraped} companies found so far.")

    # ── Download buttons ─────────────────────────────────────────────
    if st.session_state.rows:
        df = pd.DataFrame(st.session_state.rows)

        st.subheader("Download Results")
        col1, col2 = st.columns(2)
        with col1:
            label = "Download CSV" if st.session_state.completed else "Download CSV (So Far)"
            st.download_button(
                label=label,
                data=to_csv(df),
                file_name="scraping_emails_results.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with col2:
            label = "Download Excel" if st.session_state.completed else "Download Excel (So Far)"
            st.download_button(
                label=label,
                data=to_excel(df),
                file_name="scraping_emails_results.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

        # Results table
        st.subheader(f"Results ({len(df)} companies)")

        email_filter = st.radio(
            "Filter by email status",
            options=["All", "Found", "Unreachable"],
            horizontal=True,
        )

        display_df = df.copy()
        if email_filter == "Found" and "email" in display_df.columns:
            display_df = display_df[display_df["email"] != "Unreachable"]
        elif email_filter == "Unreachable" and "email" in display_df.columns:
            display_df = display_df[display_df["email"] == "Unreachable"]

        st.dataframe(
            display_df,
            use_container_width=True,
            height=600,
            column_config={
                "name": st.column_config.TextColumn("Company Name", width="medium"),
                "email": st.column_config.TextColumn("Email", width="medium"),
                "rating": st.column_config.TextColumn("Rating", width="small"),
                "reviews_count": st.column_config.TextColumn("Reviews", width="small"),
                "location": st.column_config.TextColumn("Location", width="medium"),
                "website_url": st.column_config.LinkColumn("Website", width="medium"),
                "profile_url": st.column_config.LinkColumn("Profile", width="medium"),
                "services": st.column_config.TextColumn("Services", width="large"),
                "source": st.column_config.TextColumn("Source", width="small"),
            },
        )
    elif not st.session_state.scraping and not st.session_state.completed:
        st.info(
            "Select a site and category from the sidebar, then click **Start Scraping** to begin."
        )

    # ── Activity log ─────────────────────────────────────────────────
    if st.session_state.log_messages:
        with st.expander("Activity Log", expanded=st.session_state.scraping):
            st.code("\n".join(st.session_state.log_messages[-50:]), language=None)

    # ── Auto-refresh while scraping (non-blocking) ───────────────────
    if st.session_state.scraping:
        time.sleep(3)
        st.rerun()


if __name__ == "__main__":
    main()
