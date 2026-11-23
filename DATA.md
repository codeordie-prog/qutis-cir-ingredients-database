# Data provenance

## Source

Rows are derived from the **Cosmetic Ingredient Review (CIR)** public catalog at [cir-reports.cir-safety.org](https://cir-reports.cir-safety.org/).

The Qutis team curates:

- Ingredient id ↔ name joins
- `normalized_names` for robust lookup in the rules engine
- Report and attachment URLs validated against CIR’s public site

## What we do not publish

- Firebase / Google Cloud Storage mirrors used in production
- Signed URLs, service account paths, or local `pdf_path` fields
- API keys or Postgres credentials

## Refresh policy

1. Export from `cir_pdfs` with `scripts/export_from_postgres.py`
2. Diff row counts and spot-check known ingredients (e.g. niacinamide, retinol)
3. Tag a GitHub release `vYYYY.MM.DD` and update `data/ingredients.csv` on `main`

## Versioning

The dataset version is the git tag on `main` or the release date in the filename when we publish dated snapshots.