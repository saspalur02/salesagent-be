-- ============================================================
-- DDL untuk sassalesagent database
-- Jalankan di pgAdmin ke database sassalesagent
-- ============================================================

-- Drop tabel lama
DROP TABLE IF EXISTS toko_vectors;
DROP TABLE IF EXISTS produk_vectors;

-- Drop index lama kalau ada
DROP INDEX IF EXISTS toko_vectors_embedding_idx;
DROP INDEX IF EXISTS produk_vectors_embedding_idx;

-- ── HuggingFace tables (384 dimensi) ─────────────────────────

CREATE TABLE IF NOT EXISTS toko_vectors_hf (
    toko_id     INTEGER PRIMARY KEY,
    kodetoko    VARCHAR(30),
    namatoko    VARCHAR(100) NOT NULL,
    alamat      VARCHAR(200),
    kota        VARCHAR(100),
    kecamatan   VARCHAR(100),
    propinsi    VARCHAR(50),
    hp          VARCHAR(30),
    piutang     NUMERIC DEFAULT 0,
    plafon      NUMERIC DEFAULT 0,
    teks_cari   TEXT,
    embedding   vector(384),
    updated_at  TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS toko_vectors_hf_idx
ON toko_vectors_hf
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

CREATE TABLE IF NOT EXISTS produk_vectors_hf (
    stock_id        INTEGER PRIMARY KEY,
    kodebarang      VARCHAR(50),
    namabarang      VARCHAR(250) NOT NULL,
    satuan          VARCHAR(50),
    kategori        VARCHAR(50),
    brandproduct    VARCHAR(50),
    merkkendaraan   VARCHAR(50),
    typekendaraan   VARCHAR(50),
    kendaraan       VARCHAR(50),
    partno          VARCHAR(50),
    teks_cari       TEXT,
    embedding       vector(384),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS produk_vectors_hf_idx
ON produk_vectors_hf
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- ── LiteLLM tables (768 dimensi) ─────────────────────────────

CREATE TABLE IF NOT EXISTS toko_vectors_litellm (
    toko_id     INTEGER PRIMARY KEY,
    kodetoko    VARCHAR(30),
    namatoko    VARCHAR(100) NOT NULL,
    alamat      VARCHAR(200),
    kota        VARCHAR(100),
    kecamatan   VARCHAR(100),
    propinsi    VARCHAR(50),
    hp          VARCHAR(30),
    piutang     NUMERIC DEFAULT 0,
    plafon      NUMERIC DEFAULT 0,
    teks_cari   TEXT,
    embedding   vector(768),
    updated_at  TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS toko_vectors_litellm_idx
ON toko_vectors_litellm
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

CREATE TABLE IF NOT EXISTS produk_vectors_litellm (
    stock_id        INTEGER PRIMARY KEY,
    kodebarang      VARCHAR(50),
    namabarang      VARCHAR(250) NOT NULL,
    satuan          VARCHAR(50),
    kategori        VARCHAR(50),
    brandproduct    VARCHAR(50),
    merkkendaraan   VARCHAR(50),
    typekendaraan   VARCHAR(50),
    kendaraan       VARCHAR(50),
    partno          VARCHAR(50),
    teks_cari       TEXT,
    embedding       vector(768),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS produk_vectors_litellm_idx
ON produk_vectors_litellm
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Cek tabel yang sudah dibuat
SELECT table_name, pg_size_pretty(pg_total_relation_size(quote_ident(table_name)))
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name LIKE '%vectors%'
ORDER BY table_name;
