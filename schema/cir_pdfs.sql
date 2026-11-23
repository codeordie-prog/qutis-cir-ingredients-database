-- Minimal cir_pdfs schema for Qutis / Nova rules-engine lookups.
-- Public dataset does not ship private storage paths or Firebase download URLs.

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

CREATE INDEX IF NOT EXISTS cir_pdfs_cir_ingredient_name_idx
    ON cir_pdfs (lower(cir_ingredient_name));

CREATE INDEX IF NOT EXISTS cir_pdfs_normalized_names_idx
    ON cir_pdfs (normalized_names);