"""
Vector Service — pgvector dengan provider embedding terpisah per entity:
  - EMBEDDING_PROVIDER_TOKO   : "huggingface" atau "litellm"
  - EMBEDDING_PROVIDER_PRODUK : "huggingface" atau "litellm"

Dimensi:
  - huggingface : 384
  - litellm     : 1536 (openai/text-embedding-3-small)
"""
import asyncpg
import litellm
from app.core.settings import get_settings
from app.core.logging import get_logger
import re

settings = get_settings()
logger = get_logger(__name__)

_vector_pool: asyncpg.Pool | None = None
_hf_model = None

# Override provider saat sync (dipakai oleh sync_embeddings.py)
_current_provider: str | None = None

EMBEDDING_DIM = {
    "huggingface": 384,
    "litellm": 1536,
}

HF_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

def clean_for_json(text: str) -> str:
    if not text:
        return ""
    # 1. Hapus karakter kontrol (non-printable)
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
    # 2. Ganti kutipan ganda dengan tunggal agar aman di JSON
    text = text.replace('"', "'")
    # 3. Bersihkan whitespace berlebih
    return " ".join(text.split())

def get_provider_toko() -> str:
    return _current_provider or settings.embedding_provider_toko


def get_provider_produk() -> str:
    return _current_provider or settings.embedding_provider_produk


def get_table_toko() -> str:
    return f"toko_vectors_{get_provider_toko()}"


def get_table_produk() -> str:
    return f"produk_vectors_{get_provider_produk()}"


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


async def embed_text(text: str, provider: str | None = None) -> list[float]:
    """Convert teks ke vector — pilih provider secara eksplisit atau dari settings."""
    p = provider or _current_provider or settings.embedding_provider_toko

    if p == "huggingface":
        model = _get_hf_model()
        vector = model.encode(text, normalize_embeddings=True)
        return vector.tolist()
    else:
        response = await litellm.aembedding(
            model=settings.embedding_model,
            input=[text],
            api_base=settings.embedding_api_base,
            api_key=settings.embedding_api_key,
        )
        return response.data[0]["embedding"]


async def setup_tables():
    """Buat semua tabel vector store."""
    pool = await get_vector_pool()
    async with pool.acquire() as conn:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")

        # HuggingFace (384 dim)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS toko_vectors_huggingface (
                toko_id INTEGER PRIMARY KEY, kodetoko VARCHAR(30),
                namatoko VARCHAR(100) NOT NULL, alamat VARCHAR(200),
                kota VARCHAR(100), kecamatan VARCHAR(100), propinsi VARCHAR(50),
                hp VARCHAR(30), piutang NUMERIC DEFAULT 0, plafon NUMERIC DEFAULT 0,
                teks_cari TEXT, embedding vector(384), updated_at TIMESTAMP DEFAULT NOW()
            );
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS toko_vectors_hf_idx
            ON toko_vectors_huggingface USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100);
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS produk_vectors_huggingface (
                stock_id INTEGER PRIMARY KEY, kodebarang VARCHAR(50),
                namabarang VARCHAR(250) NOT NULL, satuan VARCHAR(50),
                kategori VARCHAR(50), brandproduct VARCHAR(50),
                merkkendaraan VARCHAR(50), typekendaraan VARCHAR(50),
                kendaraan VARCHAR(50), partno VARCHAR(50),
                teks_cari TEXT, embedding vector(384), updated_at TIMESTAMP DEFAULT NOW()
            );
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS produk_vectors_hf_idx
            ON produk_vectors_huggingface USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100);
        """)

        # LiteLLM (1536 dim)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS toko_vectors_litellm (
                toko_id INTEGER PRIMARY KEY, kodetoko VARCHAR(30),
                namatoko VARCHAR(100) NOT NULL, alamat VARCHAR(200),
                kota VARCHAR(100), kecamatan VARCHAR(100), propinsi VARCHAR(50),
                hp VARCHAR(30), piutang NUMERIC DEFAULT 0, plafon NUMERIC DEFAULT 0,
                teks_cari TEXT, embedding vector(1536), updated_at TIMESTAMP DEFAULT NOW()
            );
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS toko_vectors_litellm_idx
            ON toko_vectors_litellm USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100);
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS produk_vectors_litellm (
                stock_id INTEGER PRIMARY KEY, kodebarang VARCHAR(50),
                namabarang VARCHAR(250) NOT NULL, satuan VARCHAR(50),
                kategori VARCHAR(50), brandproduct VARCHAR(50),
                merkkendaraan VARCHAR(50), typekendaraan VARCHAR(50),
                kendaraan VARCHAR(50), partno VARCHAR(50),
                teks_cari TEXT, embedding vector(1536), updated_at TIMESTAMP DEFAULT NOW()
            );
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS produk_vectors_litellm_idx
            ON produk_vectors_litellm USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100);
        """)

    logger.info("vector_tables_ready",
                toko_table=get_table_toko(),
                produk_table=get_table_produk())


async def search_toko(query: str, limit: int = 200) -> list[dict]:
    query_vector = await embed_text(query, provider=get_provider_toko())
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
            str(query_vector), limit,
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


async def search_produk(query: str, limit: int = 50) -> list[dict]:
    provider = get_provider_produk()
    table = get_table_produk()

    print("\n" + "="*60)
    print("🔍 [DEBUG search_produk — VECTOR SEARCH]")
    print("="*60)
    print(f"Query       : '{query}'")
    print(f"Provider    : {provider}")
    print(f"Table       : {table}")
    print(f"Limit       : {limit}")
    print(f"SQL (pgAdmin):")
    print(f"  SELECT stock_id, kodebarang, namabarang, satuan,")
    print(f"         kategori, brandproduct, merkkendaraan,")
    print(f"         typekendaraan, kendaraan, partno")
    print(f"  FROM {table}")
    print(f"  ORDER BY embedding <=> '<vector hasil embed>'::vector")
    print(f"  LIMIT {limit};")
    print("="*60 + "\n")

    query_vector = await embed_text(query, provider=provider)
    pool = await get_vector_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT stock_id, kodebarang, namabarang, satuan,
                   kategori, brandproduct, merkkendaraan,
                   typekendaraan, kendaraan, partno,
                   1 - (embedding <=> $1::vector) AS similarity
            FROM {table}
            WHERE kodebarang NOT ILIKE 'SB%'
              AND kodebarang NOT ILIKE 'SE%'
            ORDER BY embedding <=> $1::vector
            LIMIT $2
            """,
            str(query_vector), limit,
        )

    print(f"📊 [search_produk RESULT]: {len(rows)} baris dari vector table")
    if rows:
        print("   Top 5 hasil:")
        for r in rows[:5]:
            print(f"   - [{r['kodebarang']}] {r['namabarang']}")
    print()

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


async def upsert_toko(toko: dict) -> None:
    teks_cari = " ".join(filter(None, [
        toko.get("namatoko", ""), toko.get("alamat", ""),
        toko.get("kota", ""), toko.get("kecamatan", ""),
        toko.get("propinsi", ""),
    ]))
    embedding = await embed_text(teks_cari, provider=get_provider_toko())
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
                kodetoko=EXCLUDED.kodetoko, namatoko=EXCLUDED.namatoko,
                alamat=EXCLUDED.alamat, kota=EXCLUDED.kota,
                kecamatan=EXCLUDED.kecamatan, propinsi=EXCLUDED.propinsi,
                hp=EXCLUDED.hp, piutang=EXCLUDED.piutang, plafon=EXCLUDED.plafon,
                teks_cari=EXCLUDED.teks_cari, embedding=EXCLUDED.embedding,
                updated_at=NOW()
            """,
            int(toko["id"]), toko.get("kodetoko"), toko.get("namatoko"),
            toko.get("alamat"), toko.get("kota"), toko.get("kecamatan"),
            toko.get("propinsi"), toko.get("hp"),
            float(toko.get("piutangb") or 0), float(toko.get("plafon") or 0),
            teks_cari, str(embedding),
        )


async def upsert_produk(produk: dict) -> None:
    # ── STEP 1: Sanitasi Data Master ──
    # Kita bersihkan setiap kolom sebelum digabung untuk pencarian (teks_cari)
    # maupun untuk disimpan mentahnya di database vector.
    raw_fields = {
        "namabarang": clean_for_json(produk.get("namabarang", "")),
        "kodebarang": clean_for_json(produk.get("kodebarang", "")),
        "brandproduct": clean_for_json(produk.get("brandproduct", "")),
        "merkkendaraan": clean_for_json(produk.get("merkkendaraan", "")),
        "typekendaraan": clean_for_json(produk.get("typekendaraan", "")),
        "kendaraan": clean_for_json(produk.get("kendaraan", "")),
        "kategori": clean_for_json(produk.get("kategori", "")),
        "partno": clean_for_json(produk.get("partno", "")),
        "satuan": clean_for_json(produk.get("satuan", "pcs"))
    }

    # ── STEP 2: Gabungkan untuk Embedding ──
    teks_cari = " ".join(filter(None, [
        raw_fields["namabarang"], raw_fields["kodebarang"],
        raw_fields["brandproduct"], raw_fields["merkkendaraan"],
        raw_fields["typekendaraan"], raw_fields["kendaraan"],
        raw_fields["kategori"], raw_fields["partno"],
    ]))

    # Ambil embedding (ini yang tadi error karena JSON rusak)
    embedding = await embed_text(teks_cari, provider=get_provider_produk())
    
    # ── STEP 3: Simpan ke Database Vector (.221) ──
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
                kodebarang=EXCLUDED.kodebarang, namabarang=EXCLUDED.namabarang,
                satuan=EXCLUDED.satuan, kategori=EXCLUDED.kategori,
                brandproduct=EXCLUDED.brandproduct, merkkendaraan=EXCLUDED.merkkendaraan,
                typekendaraan=EXCLUDED.typekendaraan, kendaraan=EXCLUDED.kendaraan,
                partno=EXCLUDED.partno, teks_cari=EXCLUDED.teks_cari,
                embedding=EXCLUDED.embedding, updated_at=NOW()
            """,
            produk["id"], 
            raw_fields["kodebarang"], 
            raw_fields["namabarang"],
            raw_fields["satuan"], 
            raw_fields["kategori"], 
            raw_fields["brandproduct"],
            raw_fields["merkkendaraan"], 
            raw_fields["typekendaraan"],
            raw_fields["kendaraan"], 
            raw_fields["partno"],
            teks_cari, 
            str(embedding),
        )