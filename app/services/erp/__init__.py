"""
ERP Client — query langsung ke PostgreSQL ERP.

2 server database:
  Server 1: mstr.toko (data toko) + mstr.stock (master produk)
  Server 2: batch.rekapstocktoday (stok harian)
"""
import asyncpg
from functools import lru_cache
from app.core.settings import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

# Connection pool — dibuat sekali, reused
_erp_pool: asyncpg.Pool | None = None
_batch_pool: asyncpg.Pool | None = None


async def get_erp_pool() -> asyncpg.Pool:
    """Connection pool ke ERP Server 1 (mstr.toko + mstr.stock)."""
    global _erp_pool
    if _erp_pool is None:
        _erp_pool = await asyncpg.create_pool(
            dsn=settings.erp_db_url,
            min_size=2,
            max_size=10,
            command_timeout=30,
        )
        logger.info("erp_pool_created", server="server1")
    return _erp_pool


async def get_batch_pool() -> asyncpg.Pool:
    """Connection pool ke ERP Server 2 (batch.rekapstocktoday)."""
    global _batch_pool
    if _batch_pool is None:
        _batch_pool = await asyncpg.create_pool(
            dsn=settings.erp_batch_db_url,
            min_size=2,
            max_size=10,
            command_timeout=30,
        )
        logger.info("erp_pool_created", server="server2")
    return _batch_pool


class ERPClient:
    """
    Query langsung ke PostgreSQL ERP.
    Tidak butuh HTTP API — langsung ke database.
    """

    # ── TOKO ────────────────────────────────────────────────────

    async def find_toko(self, nama_toko: str, alamat: str = "") -> list[dict]:
        """
        Cari toko di mstr.toko berdasarkan nama dan/atau alamat.
        Pakai ILIKE untuk pencarian case-insensitive dan partial match.
        """
        pool = await get_erp_pool()
        async with pool.acquire() as conn:
            if alamat:
                rows = await conn.fetch(
                    """
                    SELECT id, kodetoko, namatoko, alamat, kota, kecamatan,
                           propinsi, hp, piutangb, piutangj, plafon, statusaktif
                    FROM mstr.toko
                    WHERE statusaktif = true
                      AND namatoko ILIKE $1
                      AND (kota ILIKE $2 OR kecamatan ILIKE $2 OR alamat ILIKE $2)
                    ORDER BY namatoko
                    LIMIT 5
                    """,
                    f"%{nama_toko}%",
                    f"%{alamat}%",
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT id, kodetoko, namatoko, alamat, kota, kecamatan,
                           propinsi, hp, piutangb, piutangj, plafon, statusaktif
                    FROM mstr.toko
                    WHERE statusaktif = true
                      AND namatoko ILIKE $1
                    ORDER BY namatoko
                    LIMIT 5
                    """,
                    f"%{nama_toko}%",
                )

        return [
            {
                "toko_id": str(row["id"]),
                "kode": row["kodetoko"],
                "name": row["namatoko"],
                "address": f"{row['alamat'] or ''}, {row['kota'] or ''}, {row['kecamatan'] or ''}".strip(", "),
                "phone": row["hp"],
                "piutang": float(row["piutangb"] or 0),
                "plafon": float(row["plafon"] or 0),
            }
            for row in rows
        ]

    async def get_toko_by_id(self, toko_id: str) -> dict | None:
        """Ambil detail toko by ID."""
        pool = await get_erp_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, kodetoko, namatoko, alamat, kota, kecamatan,
                       propinsi, hp, piutangb, piutangj, plafon, statusaktif
                FROM mstr.toko
                WHERE id = $1
                """,
                int(toko_id),
            )
        if not row:
            return None
        return {
            "toko_id": str(row["id"]),
            "kode": row["kodetoko"],
            "name": row["namatoko"],
            "address": f"{row['alamat'] or ''}, {row['kota'] or ''}, {row['kecamatan'] or ''}".strip(", "),
            "phone": row["hp"],
            "piutang": float(row["piutangb"] or 0),
            "plafon": float(row["plafon"] or 0),
        }

    # ── PRODUK ───────────────────────────────────────────────────

    async def get_products(self, active_only: bool = True) -> list[dict]:
        """
        Ambil semua produk dari mstr.stock.
        Dipakai untuk pencarian produk oleh AI Agent.
        """
        pool = await get_erp_pool()
        async with pool.acquire() as conn:
            query = """
                SELECT id, kodebarang, namabarang, satuan,
                       kategori, subkategori, brandproduct,
                       keterangan, groupstock
                FROM mstr.stock
            """
            if active_only:
                query += " WHERE statusaktif = true"
            query += " ORDER BY namabarang"

            rows = await conn.fetch(query)

        return [
            {
                "stock_id": row["id"],
                "code": row["kodebarang"] or "",
                "name": row["namabarang"] or "",
                "uom": row["satuan"] or "pcs",
                "category": row["kategori"] or "",
                "sub_category": row["subkategori"] or "",
                "brand": row["brandproduct"] or "",
                "group": row["groupstock"] or "",
                "alias": f"{row['brandproduct'] or ''} {row['namabarang'] or ''}".strip(),
            }
            for row in rows
        ]

    async def search_products(self, query: str, limit: int = 5) -> list[dict]:
        """
        Cari spare part dengan ILIKE.
        Support pencarian by: kode part, nama part, merk kendaraan,
        type kendaraan, brand produk, kategori.
        """
        pool = await get_erp_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, kodebarang, namabarang, satuan,
                       kategori, subkategori, brandproduct,
                       merkkendaraan, typekendaraan, kendaraan,
                       partno, groupstock
                FROM mstr.stock
                WHERE statusaktif = true
                  AND (
                    namabarang ILIKE $1
                    OR kodebarang ILIKE $1
                    OR brandproduct ILIKE $1
                    OR merkkendaraan ILIKE $1
                    OR typekendaraan ILIKE $1
                    OR kendaraan ILIKE $1
                    OR partno ILIKE $1
                    OR kategori ILIKE $1
                  )
                ORDER BY namabarang
                LIMIT $2
                """,
                f"%{query}%",
                limit,
            )

        return [
            {
                "stock_id": row["id"],
                "code": row["kodebarang"] or "",
                "name": row["namabarang"] or "",
                "uom": row["satuan"] or "pcs",
                "category": row["kategori"] or "",
                "brand": row["brandproduct"] or "",
                "kendaraan": row["kendaraan"] or "",
                "merk_kendaraan": row["merkkendaraan"] or "",
                "type_kendaraan": row["typekendaraan"] or "",
                "part_no": row["partno"] or "",
            }
            for row in rows
        ]

    # ── STOK ─────────────────────────────────────────────────────

    async def get_stock(self, product_code: str) -> dict:
        """
        Cek stok dari batch.rekapstocktoday di Server 2.
        Join ke mstr.stock (Server 1) tidak bisa langsung karena beda server —
        kita cari stock_id dulu dari Server 1, lalu query Server 2.
        """
        # Step 1: Cari stock_id dari Server 1
        erp_pool = await get_erp_pool()
        async with erp_pool.acquire() as conn:
            stock_row = await conn.fetchrow(
                "SELECT id, namabarang, satuan FROM mstr.stock WHERE kodebarang = $1",
                product_code,
            )

        if not stock_row:
            return {
                "product_code": product_code,
                "qty_available": 0,
                "uom": "pcs",
                "warehouse": "Gudang Utama",
            }

        stock_id = stock_row["id"]

        # Step 2: Cek stok di Server 2
        batch_pool = await get_batch_pool()
        async with batch_pool.acquire() as conn:
            batch_row = await conn.fetchrow(
                """
                SELECT stokakhir, stokgudang, tanggal
                FROM batch.rekapstocktoday
                WHERE stockid = $1
                ORDER BY tanggal DESC
                LIMIT 1
                """,
                stock_id,
            )

        qty = int(batch_row["stokakhir"] or 0) if batch_row else 0

        return {
            "product_code": product_code,
            "stock_id": stock_id,
            "product_name": stock_row["namabarang"],
            "qty_available": qty,
            "uom": stock_row["satuan"] or "pcs",
            "warehouse": "Gudang Utama",
            "last_updated": str(batch_row["tanggal"]) if batch_row else "-",
        }

    async def get_stock_by_id(self, stock_id: int) -> dict:
        """Cek stok by stock_id langsung."""
        batch_pool = await get_batch_pool()
        async with batch_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT stokakhir, stokgudang, tanggal
                FROM batch.rekapstocktoday
                WHERE stockid = $1
                ORDER BY tanggal DESC
                LIMIT 1
                """,
                stock_id,
            )
        return {
            "stock_id": stock_id,
            "qty_available": int(row["stokakhir"] or 0) if row else 0,
            "warehouse": "Gudang Utama",
        }

    # ── SALES ORDER ──────────────────────────────────────────────

    async def create_sales_order(self, payload: dict) -> dict:
        """
        Buat Sales Order di ERP.
        Untuk sekarang kita log dulu — implementasi insert ke tabel SO
        akan disesuaikan dengan struktur tabel SO di ERP kamu.

        TODO: Sesuaikan dengan tabel SO di ERP kamu.
        """
        toko_id = payload.get("toko_id", "")
        lines = payload.get("lines", [])
        note = payload.get("note", "")

        logger.info(
            "create_so_requested",
            toko_id=toko_id,
            item_count=len(lines),
            note=note,
        )

        total = sum(
            item.get("qty", 0) * item.get("price", 0)
            for item in lines
        )

        # TODO: Insert ke tabel SO ERP kamu di sini
        # Contoh:
        # pool = await get_erp_pool()
        # async with pool.acquire() as conn:
        #     so_id = await conn.fetchval(
        #         "INSERT INTO trx.salesorder (...) VALUES (...) RETURNING id",
        #         ...
        #     )

        import uuid
        so_number = f"SO-WA-{uuid.uuid4().hex[:8].upper()}"

        return {
            "so_number": so_number,
            "status": "draft",
            "total": total,
            "estimated_delivery": "2-3 hari kerja",
        }

    # ── AR / PIUTANG ─────────────────────────────────────────────

    async def get_customer_ar(self, toko_id: str) -> dict:
        """Ambil info piutang toko dari mstr.toko."""
        toko = await self.get_toko_by_id(toko_id)
        if not toko:
            return {
                "toko_id": toko_id,
                "outstanding": 0,
                "overdue": 0,
                "credit_limit": 0,
                "available_credit": 0,
            }
        piutang = toko.get("piutang", 0)
        plafon = toko.get("plafon", 0)
        return {
            "toko_id": toko_id,
            "outstanding": piutang,
            "overdue": 0,
            "credit_limit": plafon,
            "available_credit": max(0, plafon - piutang),
        }
