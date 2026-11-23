"""
Export a public CIR ingredient index CSV from Postgres (cir_pdfs).

Strips private storage URLs (Firebase/GCS) and keeps CIR-public attachment links.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from pathlib import Path
from typing import Any

try:
    import psycopg2
except ImportError as exc:  # pragma: no cover
    raise SystemExit("psycopg2 is required: pip install psycopg2-binary") from exc

_REPO_ROOT = Path(__file__).resolve().parents[1]

_PUBLIC_CSV_COLUMNS: tuple[str, ...] = (
    "ingredient_id",
    "cir_ingredient_name",
    "normalized_names",
    "function",
    "report_url",
    "attachment_url",
    "pdf_name",
    "pdf_source_url",
)

_PRIVATE_URL_MARKERS: tuple[str, ...] = (
    "firebasestorage.googleapis.com",
    "storage.googleapis.com",
    "googleusercontent.com",
    "/dawagpn",
    "dawagpn.firebasestorage",
    "dawagpn.appspot.com",
)

_CIR_ATTACHMENT_RE = re.compile(
    r"^https://cir-reports\.cir-safety\.org/view-attachment/\?id=",
    re.IGNORECASE,
)


def _resolve_password() -> str:
    """Resolve Postgres password from common environment variable names."""
    for key in (
        "POSTGRESS_PASSWORD",
        "POSTGRES_PASSWORD",
        "CLOUD_POSTGRES_PASSWORD",
        "postgres_password",
    ):
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return ""


def _is_private_url(url: str) -> bool:
    """Return True when URL points at private Qutis/Firebase storage."""
    lowered = url.lower()
    return any(marker in lowered for marker in _PRIVATE_URL_MARKERS)


def _pick_public_pdf_url(
    *,
    attachment_url: str,
    download_url: str,
    report_url: str,
) -> str:
    """
  Choose a public PDF/attachment URL suitable for open distribution.

  Args:
      attachment_url: CIR attachment URL from the database.
      download_url: Legacy download URL (often Firebase).
      report_url: CIR ingredient status report page.

  Returns:
      str: Public URL for PDF fetch, or empty string.
  """
    for candidate in (attachment_url.strip(), download_url.strip()):
        if not candidate or _is_private_url(candidate):
            continue
        if _CIR_ATTACHMENT_RE.match(candidate) or "cir-reports.cir-safety.org" in candidate:
            return candidate
        if candidate.startswith("https://cir-reports.cir-safety.org"):
            return candidate
    # Report page is useful metadata but not a direct PDF; leave pdf_source empty.
    _ = report_url
    return ""


def _normalize_missing(value: Any) -> str:
    """Coerce database values to stripped strings."""
    if value is None:
        return ""
    return str(value).strip()


def _fetch_rows(
    *,
    host: str,
    port: str,
    database: str,
    user: str,
    password: str,
    table: str,
) -> list[dict[str, str]]:
    """
    Load ingredient rows from Postgres.

    Args:
        host: Database host.
        port: Database port.
        database: Database name.
        user: Database user.
        password: Database password.
        table: Table name (default cir_pdfs).

    Returns:
        list[dict[str, str]]: Sanitized row dictionaries.
    """
    conn = psycopg2.connect(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
        sslmode=os.environ.get("POSTGRES_SSLMODE", "require"),
    )
    try:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            ORDER BY ordinal_position;
            """,
            (table,),
        )
        col_names = {str(row[0]) for row in cur.fetchall()}

        def col(name: str, fallback: str = "''") -> str:
            if name in col_names:
                return f'"{name}"'
            return fallback

        ingredient_id = f"COALESCE({col('ingredient_id')}, {col('cir_ingredient_id', "''")}, '')"
        name_col = col("cir_ingredient_name")
        norm_col = col("normalized_names")
        function_col = f"COALESCE({col('function')}, {col('Function', "'unknown'")}, 'unknown')"
        report_col = col("report_url")
        attachment_col = f"COALESCE({col('attachment_url')}, {col('attachment_view_url', "''")}, '')"
        download_col = col("download_url")
        pdf_name_col = col("pdf_name")

        query = f"""
            SELECT
                {ingredient_id} AS ingredient_id,
                COALESCE({name_col}, '') AS cir_ingredient_name,
                COALESCE({norm_col}, '') AS normalized_names,
                {function_col} AS function,
                COALESCE({report_col}, '') AS report_url,
                {attachment_col} AS attachment_url,
                COALESCE({download_col}, '') AS download_url,
                COALESCE({pdf_name_col}, '') AS pdf_name
            FROM "{table}"
            WHERE COALESCE({name_col}, '') <> ''
            ORDER BY lower(COALESCE({name_col}, ''));
        """
        cur.execute(query)
        rows: list[dict[str, str]] = []
        for record in cur.fetchall():
            attachment_url = _normalize_missing(record[5])
            download_url = _normalize_missing(record[6])
            if _is_private_url(attachment_url):
                attachment_url = ""
            report_url = _normalize_missing(record[4])
            pdf_source = _pick_public_pdf_url(
                attachment_url=attachment_url,
                download_url=download_url,
                report_url=report_url,
            )
            if not attachment_url and pdf_source:
                attachment_url = pdf_source
            rows.append(
                {
                    "ingredient_id": _normalize_missing(record[0]),
                    "cir_ingredient_name": _normalize_missing(record[1]),
                    "normalized_names": _normalize_missing(record[2]),
                    "function": _normalize_missing(record[3]) or "unknown",
                    "report_url": report_url,
                    "attachment_url": attachment_url,
                    "pdf_name": _normalize_missing(record[7]),
                    "pdf_source_url": pdf_source,
                }
            )
        return rows
    finally:
        conn.close()


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    """Write public CSV with a fixed column order."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(_PUBLIC_CSV_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    """
    CLI entrypoint.

    Returns:
        int: Process exit code.
    """
    parser = argparse.ArgumentParser(description="Export public CIR ingredient CSV from Postgres")
    parser.add_argument("--host", default=os.environ.get("POSTGRES_HOST", ""))
    parser.add_argument("--port", default=os.environ.get("POSTGRES_PORT", "5432"))
    parser.add_argument("--database", default=os.environ.get("POSTGRES_DATABASE", ""))
    parser.add_argument("--user", default=os.environ.get("POSTGRES_USER", "postgres"))
    parser.add_argument("--table", default=os.environ.get("POSTGRES_TABLE", "cir_pdfs"))
    parser.add_argument(
        "--output",
        type=Path,
        default=_REPO_ROOT / "data" / "ingredients.csv",
        help="Output CSV path",
    )
    args = parser.parse_args()

    password = _resolve_password()
    missing = [
        label
        for label, value in (
            ("POSTGRES_HOST", args.host),
            ("POSTGRES_DATABASE", args.database),
            ("POSTGRES_PASSWORD", password),
        )
        if not value
    ]
    if missing:
        print(f"ERROR: missing required settings: {', '.join(missing)}", file=sys.stderr)
        return 1

    rows = _fetch_rows(
        host=args.host,
        port=str(args.port),
        database=args.database,
        user=args.user,
        password=password,
        table=args.table,
    )
    with_pdf = sum(1 for row in rows if row.get("pdf_source_url"))
    print(f"Fetched {len(rows)} rows ({with_pdf} with public pdf_source_url)")
    _write_csv(args.output, rows)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())