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

## Using this data with Nova (Pinecone + PDF storage)

Importing the CSV gives you **ingredient metadata and public CIR links**. A full **Qutis product safety check** in [Nova](https://github.com/codeordie-prog/Nova) also needs a **vector search** stack: Pinecone for embeddings and a **stable PDF URL** per row for the rules engine to download, chunk, and index report text.

### 1. Pinecone index

Create a serverless Pinecone index compatible with Nova’s rules engine (defaults in code):

| Setting | Value |
|---------|--------|
| Index name | `qutis-index` |
| Dimensions | `1536` |
| Metric | `cosine` |

In Nova `.env` set:

- `PINECONE_API_KEY_QUTIS` — your Pinecone API key  
- `OPENAI_API_KEY_QUTIS` — used for `text-embedding-3-small` when indexing and querying chunks  

From the Nova repo you can create the index once:

```bash
cd /path/to/Nova
poetry run python -m dermascan.rules_engine.vector_store.build_index
```

Vectors are stored under the `cir` namespace inside that index. On the first safety check for an ingredient, Nova **lazy-indexes** the PDF (download → extract → embed → upsert) if it is not already in Pinecone.

### 2. PDF hosting (your S3, Firebase, GCS, or similar)

This dataset does **not** ship PDF files or production Firebase mirrors. Each row includes **`pdf_source_url`** / **`attachment_url`** pointing at the **public CIR** viewer.

For production-like behavior you should:

1. Use `pdf_source_url` (or the CIR `attachment_view_url`) to **download** each report PDF (respect CIR terms and rate limits).  
2. Upload PDFs to **your** object storage (AWS S3, Google Cloud Storage, Firebase Storage, Azure Blob, etc.).  
3. Update Postgres `cir_pdfs.download_url` (and optionally `storage_bucket` / `storage_path`) to **HTTPS URLs** your Nova workers can fetch.

The rules engine loads PDFs via `download_url` when building the Pinecone index. You can start locally with **`download_url` = public CIR URLs** (as `import_to_postgres.py` does); mirroring to your own bucket improves reliability and speed when you run many safety checks.

### 3. End-to-end checklist

1. Import `data/ingredients.csv` into Postgres (`POSTGRES_TABLE=cir_pdfs`).  
2. Ensure each row used in product review has a fetchable `download_url` (public CIR or your storage).  
3. Configure `PINECONE_API_KEY_QUTIS`, `OPENAI_API_KEY_QUTIS`, and `REDIS_URL` in Nova.  
4. Create the `qutis-index` Pinecone index.  
5. Run Nova workers and trigger a product review — indexing runs on demand per ingredient.

More detail: Nova `README.md` (§ PostgreSQL & rules engine) and `dermascan/rules_engine/vector_store/search.md`.

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