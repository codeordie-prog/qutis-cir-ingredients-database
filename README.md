# Qutis CIR ingredients database

Open index of cosmetic ingredients mapped to **public [CIR](https://cir-reports.cir-safety.org/)** safety reports. Used by the [Nova](https://github.com/codeordie-prog/Nova) rules engine for product ingredient review.

This repository ships **metadata and public CIR URLs only**. Private Firebase/GCS PDF mirrors are **not** included.

## Contents

| Path | Description |
|------|-------------|
| `data/ingredients.csv` | Curated ingredient index (one row per CIR ingredient) |
| `schema/cir_pdfs.sql` | Postgres table used by Nova (`POSTGRES_TABLE=cir_pdfs`) |
| `scripts/import_to_postgres.py` | Load CSV into local or staging Postgres |
| `scripts/export_from_postgres.py` | Regenerate CSV from a `cir_pdfs` table (maintainers) |

### CSV columns

| Column | Purpose |
|--------|---------|
| `ingredient_id` | Stable CIR / CRM ingredient id |
| `cir_ingredient_name` | INCI-style name |
| `normalized_names` | Lowercase alnum key for fuzzy match |
| `function` | Cosmetic function label |
| `report_url` | CIR ingredient status page |
| `attachment_url` | Public CIR PDF viewer URL |
| `pdf_name` | Original PDF filename when known |
| `pdf_source_url` | Public URL used to fetch report text (usually same as `attachment_url`) |

Nova’s vector indexer reads **`download_url`** on import; `import_to_postgres.py` sets `download_url = pdf_source_url` so local dev works without Firebase.

## Quick start (local Postgres)

```bash
git clone https://github.com/codeordie-prog/qutis-cir-ingredients-database.git
cd qutis-cir-ingredients-database

# Optional: create empty DB and apply schema
psql "$DATABASE_URL" -f schema/cir_pdfs.sql

export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DATABASE=postgres
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=your_password

pip install psycopg2-binary
python scripts/import_to_postgres.py --truncate
```

Point Nova `.env` at the same database (`POSTGRES_TABLE=cir_pdfs`) and run product-review flows.

## Regenerate CSV (maintainers)

Requires read access to the production `cir_pdfs` table:

```bash
export POSTGRES_HOST=...
export POSTGRES_DATABASE=qutis_db
export POSTGRES_PASSWORD=...
python scripts/export_from_postgres.py --output data/ingredients.csv
```

Private `download_url` values (Firebase, `dawagpn` buckets) are stripped; only CIR-public links are kept.

## License

- **Index curation** (this CSV and scripts): [CC BY 4.0](LICENSE).
- **CIR report text and PDFs** remain subject to CIR / Personal Care Products Council terms; this repo provides **links**, not redistributed report files.

## Attribution

When you use this dataset, cite:

> Qutis CIR Ingredients Database, https://github.com/codeordie-prog/qutis-cir-ingredients-database

Ingredient safety assessments are from the **Cosmetic Ingredient Review (CIR)**.