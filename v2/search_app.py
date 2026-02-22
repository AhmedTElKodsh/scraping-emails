"""Scraping-Emails v2 — Database-backed search dashboard.

Run from project root:
    streamlit run v2/search_app.py
"""

import subprocess
import sys
import os
import logging

# Ensure project root is on sys.path so both `v2.*` and `utils.*` imports work
# regardless of how Streamlit launches this file.
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import pandas as pd
import streamlit as st

from v2.db.database import Database
from utils.export import to_csv, to_excel

logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Company Search Engine",
    page_icon="magnifying_glass",
    layout="wide",
    initial_sidebar_state="expanded",
)


def get_db():
    db = Database()
    db.connect()
    return db


def main():
    db = get_db()
    page = st.sidebar.radio("Navigate", ["Search", "Admin"])

    if page == "Search":
        render_search_page(db)
    else:
        render_admin_page(db)


def render_search_page(db: Database):
    st.title("Company Search Engine")
    st.caption("Search B2B companies from Clutch.co and Sortlist.com")

    # ── Sidebar filters ──────────────────────────────────────────
    with st.sidebar:
        st.header("Filters")

        source = st.selectbox("Source", ["Both", "Clutch.co", "Sortlist.com"])

        all_services = db.get_all_services()
        service = st.selectbox("Service", ["All"] + all_services)

        field = None
        if service != "All":
            all_fields = db.get_fields_for_service(service)
            field_choice = st.selectbox("Field / Focus", ["All"] + all_fields)
            if field_choice != "All":
                field = field_choice

        all_countries = db.get_all_countries()
        country_choice = st.selectbox("Country / Location", ["All"] + all_countries)

        st.subheader("Rating")
        min_rating, max_rating = st.slider("Rating Range", 0.0, 5.0, (0.0, 5.0), 0.1)

        has_email = st.selectbox("Has Email", ["Any", "Yes", "No"])

    # ── Search bar ───────────────────────────────────────────────
    name_search = st.text_input("Search by company name", placeholder="Type company name...")

    # ── Build filters ────────────────────────────────────────────
    filters = dict(
        source=None if source == "Both" else source,
        service=None if service == "All" else service,
        field=field,
        country=None if country_choice == "All" else country_choice,
        min_rating=min_rating if min_rating > 0 else None,
        max_rating=max_rating if max_rating < 5.0 else None,
        has_email=True if has_email == "Yes" else (False if has_email == "No" else None),
        name_search=name_search if name_search else None,
    )

    # Only show companies that have been processed (email extraction attempted)
    filters["email_processed"] = True
    results, total = db.search_companies(**filters, limit=500)

    # ── Stats row ────────────────────────────────────────────────
    stats = db.get_stats()
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Companies", f"{stats['total']:,}")
    col2.metric("With Email", f"{stats['with_email']:,}")
    col3.metric("Contact Forms", f"{stats['with_contact_form']:,}")
    col4.metric("Clutch.co", f"{stats['clutch_count']:,}")
    col5.metric("Sortlist.com", f"{stats['sortlist_count']:,}")

    # ── Results ──────────────────────────────────────────────────
    st.subheader(f"Results ({total:,} companies)")

    if results:
        df = pd.DataFrame(results)

        # Select and reorder display columns
        display_cols = [
            c for c in [
                "name", "email", "contact_form_url", "rating", "reviews_count",
                "location", "website_url", "profile_url", "services",
                "source", "category", "sub_category",
                "min_project", "hourly_rate", "employees", "team_size", "tagline",
            ]
            if c in df.columns
        ]
        df_display = df[display_cols]

        # Download buttons
        dcol1, dcol2 = st.columns(2)
        with dcol1:
            st.download_button(
                "Download CSV", to_csv(df_display), "companies.csv", "text/csv",
                use_container_width=True,
            )
        with dcol2:
            st.download_button(
                "Download Excel", to_excel(df_display), "companies.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

        st.dataframe(
            df_display,
            use_container_width=True,
            height=600,
            column_config={
                "name": st.column_config.TextColumn("Company Name", width="medium"),
                "email": st.column_config.TextColumn("Email", width="medium"),
                "contact_form_url": st.column_config.LinkColumn("Contact Form", width="small"),
                "rating": st.column_config.NumberColumn("Rating", format="%.1f", width="small"),
                "reviews_count": st.column_config.NumberColumn("Reviews", width="small"),
                "location": st.column_config.TextColumn("Location", width="medium"),
                "website_url": st.column_config.LinkColumn("Website", width="medium"),
                "profile_url": st.column_config.LinkColumn("Profile", width="medium"),
                "services": st.column_config.TextColumn("Services", width="large"),
                "source": st.column_config.TextColumn("Source", width="small"),
                "category": st.column_config.TextColumn("Service", width="small"),
                "sub_category": st.column_config.TextColumn("Field", width="small"),
            },
        )
    else:
        st.info("No companies match your filters. Try adjusting the search criteria.")


def render_admin_page(db: Database):
    st.title("Admin Panel")

    # Stats
    stats = db.get_stats()
    st.subheader("Database Statistics")
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total", f"{stats['total']:,}")
    col2.metric("Emails", f"{stats['with_email']:,}")
    col3.metric("Forms", f"{stats['with_contact_form']:,}")
    col4.metric("Clutch", f"{stats['clutch_count']:,}")
    col5.metric("Sortlist", f"{stats['sortlist_count']:,}")

    st.divider()

    # Progress table
    st.subheader("Scrape Progress")
    progress = db.get_scrape_progress()
    if progress:
        progress_df = pd.DataFrame(progress)
        # Color code status
        st.dataframe(
            progress_df,
            use_container_width=True,
            column_config={
                "status": st.column_config.TextColumn("Status", width="small"),
                "source": st.column_config.TextColumn("Source", width="small"),
                "service": st.column_config.TextColumn("Service", width="small"),
                "field": st.column_config.TextColumn("Field", width="medium"),
                "companies_found": st.column_config.NumberColumn("Companies", width="small"),
                "error_message": st.column_config.TextColumn("Error", width="large"),
            },
        )

        # Summary counts
        total_tasks = len(progress)
        completed = sum(1 for p in progress if p["status"] == "completed")
        failed = sum(1 for p in progress if p["status"] == "failed")
        pending = sum(1 for p in progress if p["status"] == "pending")
        st.caption(f"Tasks: {completed} completed, {failed} failed, {pending} pending / {total_tasks} total")
    else:
        st.info("No scrape data yet. Run the scraper first.")

    st.divider()

    # Trigger scrape
    st.subheader("Trigger Scrape")
    st.warning("This starts a background scraping process. May take hours for all categories.")

    scol1, scol2, scol3 = st.columns(3)
    with scol1:
        site_choice = st.selectbox("Site", ["Both", "Clutch.co", "Sortlist.com"])
    with scol2:
        max_pages = st.number_input("Max Pages / Category", min_value=1, max_value=50, value=10)
    with scol3:
        proxy = st.text_input("Proxy URL", type="password", placeholder="http://user:pass@host:port")

    bcol1, bcol2 = st.columns(2)
    with bcol1:
        if st.button("Start Full Scrape", type="primary", use_container_width=True):
            cmd = [sys.executable, "-m", "v2.scrape_all", "--max-pages", str(max_pages)]
            if site_choice != "Both":
                cmd.extend(["--site", site_choice])
            if proxy:
                cmd.extend(["--proxy", proxy])
            subprocess.Popen(cmd)
            st.success("Scraper started in background. Refresh to see progress.")

    with bcol2:
        if st.button("Extract Emails Only", use_container_width=True):
            cmd = [sys.executable, "-m", "v2.scrape_all", "--emails-only"]
            if proxy:
                cmd.extend(["--proxy", proxy])
            subprocess.Popen(cmd)
            st.success("Email extraction started in background.")


if __name__ == "__main__":
    main()
