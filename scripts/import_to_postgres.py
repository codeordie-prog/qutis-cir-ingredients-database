"""
Import public ingredients.csv into Postgres cir_pdfs for local Qutis / Nova dev.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from pathlib import Path

try:
    import psycopg2
    from psycopg2.extras import execute_batch
except ImportError as exc:  # pragma: no cover
    raise SystemExit("psycopg2 is required: pip install psycopg2-binary") from exc

_REPO_ROOT = Path(__file__).resolve().parents[1]

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS cir_pdfs (
    id BIGSERIAL PRIMARY KEY,
    ingredient_id TEXT,
    cir_ingredient_name TEXT NOT NULL,
    normalized_names TEXT,
    function TEXT DEFAULT 'unknown',
    report_url TEXT,
    attachment_url TEXT,
    pdf_name TEXT,
    download_url TEXT,
    storage_bucket TEXT,
    storage_path TEXT,
    storage_updated_at TIMESTAMP
);
"""

_UPSERT_SQL = """
INSERT INTO cir_pdfs (
    ingredient_id,
    cir_ingredient_name,
    normalized_names,
    function,
    report_url,
    attachment_url,
    pdf_name,
    download_url
) VALUES (
    %(ingredient_id)s,
    %(cir_ingredient_name)s,
    %(normalized_names)s,
    %(function)s,
    %(report_url)s,
    %(attachment_url)s,
    %(pdf_name)s,
    %(download_url)s
);
"""


def _resolve_password() -> str:
    """Resolve Postgres password from environment."""
    for key in ("POSTGRESS_PASSWORD", "POSTGRES_PASSWORD", "postgres_password"):
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return ""


def _normalize_name(name: str) -> str:
    """Lowercase alnum-only normalization (matches Nova rules engine)."""
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def _row_to_record(raw: dict[str, str]) -> dict[str, str]:
    """
    Convert a public CSV row into a cir_pdfs insert record.

    Args:
        raw: CSV row dictionary.

    Returns:
        dict[str, str]: Values for INSERT.
    """
    name = (raw.get("cir_ingredient_name") or "").strip()
    normalized = (raw.get("normalized_names") or "").strip()
    if not normalized and name:
        normalized = _normalize_name(name)
    attachment = (raw.get("attachment_url") or "").strip()
    pdf_source = (raw.get("pdf_source_url") or attachment).strip()
    download_url = pdf_source or attachment
    return {
        "ingredient_id": (raw.get("ingredient_id") or "").strip(),
        "cir_ingredient_name": name,
        "normalized_names": normalized,
        "function": (raw.get("function") or "unknown").strip() or "unknown",
        "report_url": (raw.get("report_url") or "").strip(),
        "attachment_url": attachment or pdf_source,
        "pdf_name": (raw.get("pdf_name") or "").strip(),
        "download_url": download_url,
    }


def main() -> int:
    """
    CLI entrypoint.

    Returns:
        int: Process exit code.
    """
    parser = argparse.ArgumentParser(description="Import ingredients.csv into Postgres cir_pdfs")
    parser.add_argument("--host", default=os.environ.get("POSTGRES_HOST", "localhost"))
    parser.add_argument("--port", default=os.environ.get("POSTGRES_PORT", "5432"))
    parser.add_argument("--database", default=os.environ.get("POSTGRES_DATABASE", "postgres"))
    parser.add_argument("--user", default=os.environ.get("POSTGRES_USER", "postgres"))
    parser.add_argument("--table", default=os.environ.get("POSTGRES_TABLE", "cir_pdfs"))
    parser.add_argument(
        "--input",
        type=Path,
        default=_REPO_ROOT / "data" / "ingredients.csv",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Truncate cir_pdfs before import (destructive)",
    )
    args = parser.parse_args()

    password = _resolve_password()
    if not args.input.is_file():
        print(f"ERROR: CSV not found: {args.input}", file=sys.stderr)
        return 1

    with args.input.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        records = [_row_to_record(row) for row in reader if row.get("cir_ingredient_name")]

    conn = psycopg2.connect(
        host=args.host,
        port=str(args.port),
        database=args.database,
        user=args.user,
        password=password,
        sslmode=os.environ.get("POSTGRES_SSLMODE", "prefer"),
    )
    try:
        cur = conn.cursor()
        cur.execute(_CREATE_TABLE_SQL)
        if args.truncate:
            cur.execute(f'TRUNCATE TABLE "{args.table}" RESTART IDENTITY;')
        execute_batch(cur, _UPSERT_SQL, records, page_size=500)
        conn.commit()
        print(f"Imported {len(records)} rows into {args.table}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())