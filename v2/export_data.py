"""Export scraped data to CSV/Excel split by service type, optionally send via Email.

Exports companies with emails and contact forms, grouped by service:
  development_emails_1.xlsx, marketing_emails_1.xlsx, ...
  development_contact_forms_1.xlsx, ...

Usage:
    python -m v2.export_data
    python -m v2.export_data --email-to you@gmail.com --email-from you@gmail.com --email-password "xxxx"
"""

import argparse
import logging
import os
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path

import pandas as pd

from v2.db.database import Database
from v2.config.settings import (
    EMAIL_TO, EMAIL_FROM, EMAIL_PASSWORD,
    DB_PATH, OUTPUT_DIR,
)

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

logger = logging.getLogger(__name__)

MAX_ROWS_PER_SHEET = 1_000_000
MAX_ROWS_PER_FILE = 50_000  # split into numbered files after this
GMAIL_MAX_ATTACHMENT_MB = 25

DISPLAY_COLUMNS = [
    "name", "email", "contact_form_url", "rating", "reviews_count",
    "location", "country", "website_url", "profile_url", "services",
    "source", "category", "sub_category",
    "min_project", "hourly_rate", "employees", "team_size", "tagline",
]


def load_data_by_service(db: Database) -> dict[str, tuple[pd.DataFrame, pd.DataFrame]]:
    """Load companies grouped by service. Returns {service: (df_emails, df_forms)}."""
    conn = db.conn

    services = [r[0] for r in conn.execute(
        "SELECT DISTINCT service FROM company_categories ORDER BY service"
    ).fetchall()]

    result = {}
    for service in services:
        df_emails = pd.read_sql_query("""
            SELECT c.*,
                   GROUP_CONCAT(DISTINCT cc2.service) AS category,
                   GROUP_CONCAT(DISTINCT cc2.field) AS sub_category
            FROM companies c
            JOIN company_categories cc ON cc.company_id = c.id AND cc.service = ?
            LEFT JOIN company_categories cc2 ON cc2.company_id = c.id
            WHERE c.email IS NOT NULL AND c.email != '' AND c.email != 'Unreachable'
            GROUP BY c.id
            ORDER BY c.rating DESC NULLS LAST, c.reviews_count DESC NULLS LAST
        """, conn, params=(service,))

        df_forms = pd.read_sql_query("""
            SELECT c.*,
                   GROUP_CONCAT(DISTINCT cc2.service) AS category,
                   GROUP_CONCAT(DISTINCT cc2.field) AS sub_category
            FROM companies c
            JOIN company_categories cc ON cc.company_id = c.id AND cc.service = ?
            LEFT JOIN company_categories cc2 ON cc2.company_id = c.id
            WHERE (c.email IS NULL OR c.email = '' OR c.email = 'Unreachable')
              AND c.contact_form_url IS NOT NULL AND c.contact_form_url != ''
            GROUP BY c.id
            ORDER BY c.rating DESC NULLS LAST, c.reviews_count DESC NULLS LAST
        """, conn, params=(service,))

        # Keep only display columns
        for df in (df_emails, df_forms):
            cols = [c for c in DISPLAY_COLUMNS if c in df.columns]
            df.drop(columns=[c for c in df.columns if c not in cols], inplace=True)

        if not df_emails.empty or not df_forms.empty:
            result[service] = (df_emails, df_forms)

    return result


def _safe_name(service: str) -> str:
    """Convert service name to safe filename: 'IT Services' -> 'it_services'."""
    return service.lower().replace(" ", "_")


def _write_numbered_excels(
    df: pd.DataFrame, output_dir: Path, prefix: str, sheet_label: str,
) -> list[Path]:
    """Write a DataFrame to numbered Excel files, splitting by MAX_ROWS_PER_FILE."""
    files = []
    if df.empty:
        return files

    chunks = [df.iloc[i:i + MAX_ROWS_PER_FILE] for i in range(0, len(df), MAX_ROWS_PER_FILE)]

    for idx, chunk in enumerate(chunks, start=1):
        path = output_dir / f"{prefix}_{idx}.xlsx"
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            chunk.to_excel(writer, index=False, sheet_name=sheet_label)
        size_mb = path.stat().st_size / (1024 * 1024)
        logger.info("    %s (%d rows, %.1f MB)", path.name, len(chunk), size_mb)
        files.append(path)

    return files


def _write_numbered_csvs(
    df: pd.DataFrame, output_dir: Path, prefix: str,
) -> list[Path]:
    """Write a DataFrame to numbered CSV files."""
    files = []
    if df.empty:
        return files

    chunks = [df.iloc[i:i + MAX_ROWS_PER_FILE] for i in range(0, len(df), MAX_ROWS_PER_FILE)]

    for idx, chunk in enumerate(chunks, start=1):
        path = output_dir / f"{prefix}_{idx}.csv"
        chunk.to_csv(path, index=False, encoding="utf-8-sig")
        size_mb = path.stat().st_size / (1024 * 1024)
        logger.info("    %s (%d rows, %.1f MB)", path.name, len(chunk), size_mb)
        files.append(path)

    return files


# ── Email delivery (Gmail SMTP) ──────────────────────────────────

def send_via_email(
    email_to: str,
    email_from: str,
    email_password: str,
    file_groups: list[tuple[str, list[Path]]],
    smtp_host: str = "smtp.gmail.com",
    smtp_port: int = 587,
) -> None:
    """Send files via Gmail, one email per service group.

    file_groups: [(subject_label, [file_paths]), ...]
    If a group exceeds 25 MB, it's split across multiple emails.
    """
    for label, files in file_groups:
        if not files:
            continue
        batches = _batch_files_by_size(files, max_mb=GMAIL_MAX_ATTACHMENT_MB)

        for i, batch in enumerate(batches, start=1):
            part_label = f" (Part {i}/{len(batches)})" if len(batches) > 1 else ""

            msg = MIMEMultipart()
            msg["From"] = email_from
            msg["To"] = email_to
            msg["Subject"] = f"Scraping Export - {label}{part_label}"

            body = f"{label}\n\nAttached files ({len(batch)}):\n"
            for f in batch:
                size_mb = f.stat().st_size / (1024 * 1024)
                body += f"  - {f.name} ({size_mb:.1f} MB)\n"
            msg.attach(MIMEText(body, "plain"))

            for filepath in batch:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(filepath.read_bytes())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f'attachment; filename="{filepath.name}"')
                msg.attach(part)

            logger.info("  Sending: %s%s (%d files)...", label, part_label, len(batch))
            try:
                with smtplib.SMTP(smtp_host, smtp_port, timeout=60) as server:
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                    server.login(email_from, email_password)
                    server.sendmail(email_from, email_to, msg.as_string())
                logger.info("  Sent.")
            except smtplib.SMTPAuthenticationError:
                logger.error("  Gmail auth failed. Check app password: https://myaccount.google.com/apppasswords")
                raise
            except Exception as e:
                logger.error("  Email send failed: %s", e)
                raise


def _batch_files_by_size(files: list[Path], max_mb: float) -> list[list[Path]]:
    """Group files into batches that fit within a size limit."""
    max_bytes = max_mb * 1024 * 1024
    batches = []
    current_batch = []
    current_size = 0

    for f in files:
        fsize = f.stat().st_size
        if current_batch and current_size + fsize > max_bytes:
            batches.append(current_batch)
            current_batch = []
            current_size = 0
        current_batch.append(f)
        current_size += fsize

    if current_batch:
        batches.append(current_batch)

    return batches


# ── Main export ───────────────────────────────────────────────────

def export_all(
    db: Database,
    output_dir: Path,
    email_to: str = "",
    email_from: str = "",
    email_password: str = "",
) -> None:
    """Export by service type, numbered files. Optionally email each service group."""
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Loading data by service...")
    data_by_service = load_data_by_service(db)

    if not data_by_service:
        logger.info("No data to export.")
        return

    email_groups: list[tuple[str, list[Path]]] = []

    for service, (df_emails, df_forms) in data_by_service.items():
        safe = _safe_name(service)
        service_files: list[Path] = []

        logger.info("")
        logger.info("--- %s: %d emails, %d contact forms ---", service, len(df_emails), len(df_forms))

        if not df_emails.empty:
            logger.info("  Emails (Excel):")
            service_files.extend(
                _write_numbered_excels(df_emails, output_dir, f"{safe}_emails", "Emails")
            )
            logger.info("  Emails (CSV):")
            service_files.extend(
                _write_numbered_csvs(df_emails, output_dir, f"{safe}_emails")
            )

        if not df_forms.empty:
            logger.info("  Contact Forms (Excel):")
            service_files.extend(
                _write_numbered_excels(df_forms, output_dir, f"{safe}_contact_forms", "Contact Forms")
            )
            logger.info("  Contact Forms (CSV):")
            service_files.extend(
                _write_numbered_csvs(df_forms, output_dir, f"{safe}_contact_forms")
            )

        if service_files:
            label = f"{service} - {len(df_emails)} emails, {len(df_forms)} contact forms"
            email_groups.append((label, service_files))

    logger.info("")
    logger.info("Export complete -> %s", output_dir)

    # Email delivery — CLI args override .env values
    to_addr = email_to or EMAIL_TO
    from_addr = email_from or EMAIL_FROM
    password = email_password or EMAIL_PASSWORD

    if to_addr and from_addr and password:
        logger.info("")
        logger.info("=" * 70)
        logger.info("SENDING EMAILS")
        logger.info("=" * 70)
        send_via_email(to_addr, from_addr, password, email_groups)
        logger.info("All emails sent.")
    elif to_addr or from_addr:
        logger.warning("Email partially configured. Need --email-to, --email-from, and --email-password.")
    else:
        logger.info("No email configured. Use --email-to/--email-from/--email-password or EMAIL_TO/EMAIL_FROM/EMAIL_PASSWORD env vars.")


def main():
    parser = argparse.ArgumentParser(description="Export scraped data by service type to CSV/Excel and send via email")
    parser.add_argument("--db", default=None, help="Database file path (default: DB_PATH from .env)")
    parser.add_argument("--output", default=None, help="Output directory (default: OUTPUT_DIR from .env)")
    parser.add_argument("--email-to", default="", help="Recipient email address")
    parser.add_argument("--email-from", default="", help="Sender Gmail address")
    parser.add_argument("--email-password", default="", help="Gmail app password (16-char)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    db = Database(args.db or DB_PATH)
    db.connect()
    try:
        export_all(
            db,
            Path(args.output or OUTPUT_DIR),
            email_to=args.email_to,
            email_from=args.email_from,
            email_password=args.email_password,
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
