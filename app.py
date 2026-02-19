"""Scraping-Emails — Streamlit Dashboard.

A free, stealth web scraping engine for B2B lead extraction from
Clutch.co and Sortlist.com with automatic email discovery.
"""

import logging
import time
import threading

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


def init_session_state():
    """Initialize session state variables."""
    defaults = {
        "data": pd.DataFrame(),
        "scraping": False,
        "completed": False,
        "stop_requested": False,
        "total_scraped": 0,
        "total_emails_found": 0,
        "log_messages": [],
        "scraper_thread": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def get_scraper(site: str, headless: bool | str = True):
    """Create the appropriate scraper for the given site."""
    if site == "Clutch.co":
        return ClutchScraper(headless=headless)
    elif site == "Sortlist.com":
        return SortlistScraper(headless=headless)
    else:
        raise ValueError(f"Unknown site: {site}")


def add_log(message: str):
    """Add a log message to the UI log (thread-safe via session_state)."""
    timestamp = time.strftime("%H:%M:%S")
    st.session_state.log_messages.append(f"[{timestamp}] {message}")
    # Keep last 100 messages
    if len(st.session_state.log_messages) > 100:
        st.session_state.log_messages = st.session_state.log_messages[-100:]


def run_scraper_thread(tasks: list[tuple[str, str, str]]):
    """Run scraping in a background thread so the UI stays responsive.

    Args:
        tasks: List of (site, category, url) tuples to scrape.
    """
    for site, category, url in tasks:
        if st.session_state.stop_requested:
            break

        scraper = get_scraper(site)
        try:
            add_log(f"Starting {site} scraper for {category}...")
            scraper.start_browser()
            email_extractor = EmailExtractor(scraper.page)
            add_log(f"Navigating to {url}")

            for company in scraper.scrape_category(url):
                if st.session_state.stop_requested:
                    add_log("Stop requested by user. Finishing...")
                    break

                # Add company to DataFrame
                new_row = pd.DataFrame([company])
                st.session_state.data = pd.concat(
                    [st.session_state.data, new_row], ignore_index=True
                )
                st.session_state.total_scraped += 1

                # Extract email
                website_url = company.get("website_url", "")
                if website_url:
                    add_log(f"Extracting email for {company.get('name', 'Unknown')}...")
                    email = email_extractor.find_email(website_url)
                    idx = len(st.session_state.data) - 1
                    st.session_state.data.at[idx, "email"] = email
                    if email != "Unreachable":
                        st.session_state.total_emails_found += 1
                        add_log(f"  Found: {email}")
                    else:
                        add_log("  Unreachable")
                else:
                    idx = len(st.session_state.data) - 1
                    st.session_state.data.at[idx, "email"] = "Unreachable"
                    add_log(f"  No website URL for {company.get('name', 'Unknown')}")

            add_log(
                f"Finished {site}/{category}: "
                f"{st.session_state.total_scraped} companies, "
                f"{st.session_state.total_emails_found} emails found."
            )

        except Exception as e:
            add_log(f"Error during {site} scraping: {e}")
            logger.exception("Scraping error for %s", site)

        finally:
            scraper.close_browser()

    st.session_state.scraping = False
    st.session_state.completed = True
    add_log("All scraping tasks complete.")


def main():
    """Main Streamlit application."""
    init_session_state()

    # Header
    st.title("📧 Scraping-Emails")
    st.markdown(
        "**Free B2B lead extraction** from Clutch.co & Sortlist.com with automatic email discovery."
    )

    # Sidebar — Configuration
    with st.sidebar:
        st.header("Configuration")

        # Site selection
        site_option = st.radio(
            "Select Site",
            options=["Clutch.co", "Sortlist.com", "Both"],
            index=0,
            disabled=st.session_state.scraping,
        )

        # Category selection based on site
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

        # Start/Stop buttons
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
            st.session_state.stop_requested = True

        # Reset button (shown after completion)
        if st.session_state.completed:
            if st.button("New Scrape", use_container_width=True):
                st.session_state.data = pd.DataFrame()
                st.session_state.scraping = False
                st.session_state.completed = False
                st.session_state.stop_requested = False
                st.session_state.total_scraped = 0
                st.session_state.total_emails_found = 0
                st.session_state.log_messages = []
                st.session_state.scraper_thread = None
                st.rerun()

        st.divider()

        # Stats
        st.subheader("Stats")
        st.metric("Companies Scraped", st.session_state.total_scraped)
        st.metric("Emails Found", st.session_state.total_emails_found)
        if st.session_state.total_scraped > 0:
            rate = (st.session_state.total_emails_found / st.session_state.total_scraped) * 100
            st.metric("Email Hit Rate", f"{rate:.1f}%")

    # Main content area — Start scraping
    if start_clicked and not st.session_state.scraping:
        st.session_state.data = pd.DataFrame()
        st.session_state.scraping = True
        st.session_state.completed = False
        st.session_state.stop_requested = False
        st.session_state.total_scraped = 0
        st.session_state.total_emails_found = 0
        st.session_state.log_messages = []

        # Launch scraper in background thread
        thread = threading.Thread(
            target=run_scraper_thread,
            args=(selected_tasks,),
            daemon=True,
        )
        st.session_state.scraper_thread = thread
        thread.start()
        st.rerun()

    # Auto-refresh while scraping is active (poll every 2 seconds)
    if st.session_state.scraping:
        time.sleep(2)
        st.rerun()

    # Download buttons (always visible when there's data)
    if not st.session_state.data.empty:
        st.subheader("Download Results")
        col1, col2 = st.columns(2)
        with col1:
            label = "Download CSV" if st.session_state.completed else "Download CSV (So Far)"
            st.download_button(
                label=label,
                data=to_csv(st.session_state.data),
                file_name="scraping_emails_results.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with col2:
            label = "Download Excel" if st.session_state.completed else "Download Excel (So Far)"
            st.download_button(
                label=label,
                data=to_excel(st.session_state.data),
                file_name="scraping_emails_results.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

    # Results table
    if not st.session_state.data.empty:
        st.subheader(f"Results ({len(st.session_state.data)} companies)")

        # Email status filter
        email_filter = st.radio(
            "Filter by email status",
            options=["All", "Found", "Unreachable"],
            horizontal=True,
        )

        display_df = st.session_state.data.copy()
        if email_filter == "Found":
            display_df = display_df[display_df["email"] != "Unreachable"]
        elif email_filter == "Unreachable":
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

    # Progress indicator while scraping
    if st.session_state.scraping:
        st.progress(0.0, text="Scraping in progress...")

    # Activity log
    if st.session_state.log_messages:
        with st.expander("Activity Log", expanded=st.session_state.scraping):
            st.code("\n".join(st.session_state.log_messages[-30:]), language=None)


if __name__ == "__main__":
    main()
