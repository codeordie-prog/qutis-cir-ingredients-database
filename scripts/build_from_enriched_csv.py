"""
Build public ingredients.csv from cir-crawler enriched_dataset.csv (offline fallback).

Use when Postgres export is unavailable; rows are aligned with cir_pdfs import.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]

_PUBLIC_COLUMNS = (
    "ingredient_id",
    "cir_ingredient_name",
    "normalized_names",
    "function",
    "report_url",
    "attachment_url",
    "pdf_name",
    "pdf_source_url",
)



def _normalize_name(name: str) -> str:
    """Lowercase alnum-only normalization."""
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def _uuid_from_url(url: str) -> str:
    """Extract attachment id suffix for pdf_name when present."""
    match = re.search(r"id=([0-9a-f-]{36})", url, re.IGNORECASE)
    return f"{match.group(1)}.pdf" if match else ""


def main() -> int:
    """
    CLI entrypoint.

    Returns:
        int: Process exit code.
    """
    parser = argparse.ArgumentParser(description="Build ingredients.csv from enriched_dataset.csv")
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Path to cir-crawler scripts/enriched_dataset.csv",
    )
    parser.add_argument("--output", type=Path, default=_REPO_ROOT / "data" / "ingredients.csv")
    args = parser.parse_args()

    if not args.source.is_file():
        print(f"ERROR: source not found: {args.source}", file=sys.stderr)
        return 1

    rows: list[dict[str, str]] = []
    with args.source.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            name = (raw.get("cir_ingredient_name") or raw.get("ingredient_name") or "").strip()
            if not name:
                continue
            attachment = (raw.get("attachment_view_url") or "").strip()
            if attachment and "cir-reports.cir-safety.org" not in attachment.lower():
                attachment = ""
            ingredient_id = (raw.get("cir_ingredient_id") or raw.get("ingredient_id") or "").strip()
            report_url = (raw.get("report_url") or "").strip()
            function = (raw.get("Function") or raw.get("function") or "unknown").strip() or "unknown"
            pdf_name = _uuid_from_url(attachment)
            rows.append(
                {
                    "ingredient_id": ingredient_id,
                    "cir_ingredient_name": name,
                    "normalized_names": _normalize_name(name),
                    "function": function,
                    "report_url": report_url,
                    "attachment_url": attachment,
                    "pdf_name": pdf_name,
                    "pdf_source_url": attachment,
                }
            )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(_PUBLIC_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)

    with_pdf = sum(1 for row in rows if row.get("pdf_source_url"))
    print(f"Wrote {len(rows)} rows ({with_pdf} with pdf_source_url) -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())