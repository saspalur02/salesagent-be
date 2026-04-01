"""
Vector Service — pgvector dengan 2 provider embedding:
  - huggingface: sentence-transformers lokal (384 dim)
  - litellm: via LiteLLM proxy (768 dim) — Gemini, OpenAI, dll

Set EMBEDDING_PROVIDER di .env untuk pilih provider.
Ganti provider → wajib re-sync data.
"""
import asyncpg
import litellm
from app.core.settings import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

_vector_pool: asyncpg.Pool | None = None
_hf_model = None

# Dimensi per provider
EMBEDDING_DIM = {
    "huggingface": 384,
    "litellm": 768,
}

HF_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def get_table_toko() -> str:
    return f"toko_vectors_{settings.embedding_provider}"


def get_table_produk() -> str:
    return f"produk_vectors_{settings.embedding_provider}"


def get_dim() -> int:
    return EMBEDDING_DIM.get(settings.embedding_provider, 768)


async def get_vector_pool() -> asyncpg.Pool:
    global _vector_pool
    if _vector_pool is None:
        _vector_pool = await asyncpg.create_pool(
            dsn=settings.pgvector_url,
            min_size=2,
            max_size=10,
            command_timeout=30,
        )
        logger.info("vector_pool_created")
    return _vector_pool


def _get_hf_model():
    global _hf_model
    if _hf_model is None:
        from sentence_transformers import SentenceTransformer
        logger.info("loading_embedding_model", model=HF_MODEL_NAME)
        _hf_model = SentenceTransformer(HF_MODEL_NAME)
        logger.info("embedding_model_loaded")
    return _hf_model


async def embed_text(text: str) -> list[float]:
    """Convert teks ke vector — pilih provider dari settings."""
    if settings.embedding_provider == "huggingface":
        model = _get_hf_model()
        vector = model.encode(text, normalize_embeddings=True)
        return vector.tolist()
    else:
        # LiteLLM provider (Gemini, OpenAI, dll)
        response = await litellm.aembedding(
            model=settings.embedding_model,
            input=[text],
            api_base=settings.embedding_api_base,
            api_key=settings.embedding_api_key,
        )
        return response.data[0]["embedding"]


async def setup_tables():
    """
    Buat semua tabel vector store (HuggingFace + LiteLLM).
    Dipanggil saat startup.
    """
    pool = await get_vector_pool()
    async with pool.acquire() as conn:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")

        # ── HuggingFace tables (384 dim) ─────────────────────────
        await conn.execute("""
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
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS toko_vectors_hf_idx
            ON toko_vectors_hf
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100);
        """)

        await conn.execute("""
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
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS produk_vectors_hf_idx
            ON produk_vectors_hf
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100);
        """)

        # ── LiteLLM tables (768 dim) ─────────────────────────────
        await conn.execute("""
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
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS toko_vectors_litellm_idx
            ON toko_vectors_litellm
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100);
        """)

        await conn.execute("""
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
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS produk_vectors_litellm_idx
            ON produk_vectors_litellm
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100);
        """)

    logger.info("vector_tables_ready",
                provider=settings.embedding_provider,
                toko_table=get_table_toko(),
                produk_table=get_table_produk())


# ── Search ───────────────────────────────────────────────────────

async def search_toko(query: str, limit: int = 200) -> list[dict]:
    """Cari toko secara semantic."""
    query_vector = await embed_text(query)
    table = get_table_toko()
    pool = await get_vector_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT toko_id, kodetoko, namatoko, alamat, kota,
                   kecamatan, hp, piutang, plafon,
                   1 - (embedding <=> $1::vector) AS similarity
            FROM {table}
            ORDER BY embedding <=> $1::vector
            LIMIT $2
            """,
            str(query_vector),
            limit,
        )

    return [
        {
            "toko_id": str(row["toko_id"]),
            "kode": row["kodetoko"],
            "name": row["namatoko"],
            "address": f"{row['alamat'] or ''}, {row['kota'] or ''}, {row['kecamatan'] or ''}".strip(", "),
            "phone": row["hp"],
            "piutang": float(row["piutang"] or 0),
            "plafon": float(row["plafon"] or 0),
            "similarity": round(float(row["similarity"]), 3),
        }
        for row in rows
    ]


async def search_produk(query: str, limit: int = 5) -> list[dict]:
    """Cari spare part secara semantic."""
    query_vector = await embed_text(query)
    table = get_table_produk()
    pool = await get_vector_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT stock_id, kodebarang, namabarang, satuan,
                   kategori, brandproduct, merkkendaraan,
                   typekendaraan, kendaraan, partno,
                   1 - (embedding <=> $1::vector) AS similarity
            FROM {table}
            ORDER BY embedding <=> $1::vector
            LIMIT $2
            """,
            str(query_vector),
            limit,
        )

    return [
        {
            "stock_id": row["stock_id"],
            "code": row["kodebarang"] or "",
            "name": row["namabarang"] or "",
            "uom": row["satuan"] or "pcs",
            "category": row["kategori"] or "",
            "brand": row["brandproduct"] or "",
            "merk_kendaraan": row["merkkendaraan"] or "",
            "type_kendaraan": row["typekendaraan"] or "",
            "kendaraan": row["kendaraan"] or "",
            "part_no": row["partno"] or "",
            "similarity": round(float(row["similarity"]), 3),
        }
        for row in rows
    ]


# ── Upsert ───────────────────────────────────────────────────────

async def upsert_toko(toko: dict) -> None:
    """Insert atau update satu toko ke vector store."""
    teks_cari = " ".join(filter(None, [
        toko.get("namatoko", ""),
        toko.get("alamat", ""),
        toko.get("kota", ""),
        toko.get("kecamatan", ""),
        toko.get("propinsi", ""),
    ]))

    embedding = await embed_text(teks_cari)
    table = get_table_toko()
    pool = await get_vector_pool()

    async with pool.acquire() as conn:
        await conn.execute(
            f"""
            INSERT INTO {table}
                (toko_id, kodetoko, namatoko, alamat, kota, kecamatan,
                 propinsi, hp, piutang, plafon, teks_cari, embedding, updated_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12::vector,NOW())
            ON CONFLICT (toko_id) DO UPDATE SET
                kodetoko    = EXCLUDED.kodetoko,
                namatoko    = EXCLUDED.namatoko,
                alamat      = EXCLUDED.alamat,
                kota        = EXCLUDED.kota,
                kecamatan   = EXCLUDED.kecamatan,
                propinsi    = EXCLUDED.propinsi,
                hp          = EXCLUDED.hp,
                piutang     = EXCLUDED.piutang,
                plafon      = EXCLUDED.plafon,
                teks_cari   = EXCLUDED.teks_cari,
                embedding   = EXCLUDED.embedding,
                updated_at  = NOW()
            """,
            int(toko["id"]),
            toko.get("kodetoko"),
            toko.get("namatoko"),
            toko.get("alamat"),
            toko.get("kota"),
            toko.get("kecamatan"),
            toko.get("propinsi"),
            toko.get("hp"),
            float(toko.get("piutangb") or 0),
            float(toko.get("plafon") or 0),
            teks_cari,
            str(embedding),
        )


async def upsert_produk(produk: dict) -> None:
    """Insert atau update satu produk ke vector store."""
    teks_cari = " ".join(filter(None, [
        produk.get("namabarang", ""),
        produk.get("kodebarang", ""),
        produk.get("brandproduct", ""),
        produk.get("merkkendaraan", ""),
        produk.get("typekendaraan", ""),
        produk.get("kendaraan", ""),
        produk.get("kategori", ""),
        produk.get("partno", ""),
    ]))

    embedding = await embed_text(teks_cari)
    table = get_table_produk()
    pool = await get_vector_pool()

    async with pool.acquire() as conn:
        await conn.execute(
            f"""
            INSERT INTO {table}
                (stock_id, kodebarang, namabarang, satuan, kategori,
                 brandproduct, merkkendaraan, typekendaraan, kendaraan,
                 partno, teks_cari, embedding, updated_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12::vector,NOW())
            ON CONFLICT (stock_id) DO UPDATE SET
                kodebarang      = EXCLUDED.kodebarang,
                namabarang      = EXCLUDED.namabarang,
                satuan          = EXCLUDED.satuan,
                kategori        = EXCLUDED.kategori,
                brandproduct    = EXCLUDED.brandproduct,
                merkkendaraan   = EXCLUDED.merkkendaraan,
                typekendaraan   = EXCLUDED.typekendaraan,
                kendaraan       = EXCLUDED.kendaraan,
                partno          = EXCLUDED.partno,
                teks_cari       = EXCLUDED.teks_cari,
                embedding       = EXCLUDED.embedding,
                updated_at      = NOW()
            """,
            produk["id"],
            produk.get("kodebarang"),
            produk.get("namabarang"),
            produk.get("satuan"),
            produk.get("kategori"),
            produk.get("brandproduct"),
            produk.get("merkkendaraan"),
            produk.get("typekendaraan"),
            produk.get("kendaraan"),
            produk.get("partno"),
            teks_cari,
            str(embedding),
        )
