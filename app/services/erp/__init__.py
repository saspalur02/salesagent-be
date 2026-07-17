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

# Import fungsi pencarian hybrid dari file toko.py agar bisa dipanggil terpusat
from .toko import find_toko_hybrid

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
            command_timeout=300,
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
            command_timeout=300,
        )
        logger.info("erp_pool_created", server="server2")
    return _batch_pool


class ERPClient:
    """
    Query langsung ke PostgreSQL ERP.
    Tidak butuh HTTP API — langsung ke database.
    """

    # ── TOKO ────────────────────────────────────────────────────

    async def get_toko_by_id(self, toko_id: str) -> dict | None:
        """Ambil detail toko by ID untuk keperluan validasi akhir."""
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

    async def get_toko_by_phone(self, wa_number: str) -> list[dict]:
        """
        Identifikasi toko dari nomor WhatsApp pengirim.

        Cek kolom `hp` DAN `telp` di mstr.toko. Nomor di DB bisa tersimpan dalam
        format apa pun (0818..., 62818..., 0062818..., pakai spasi/strip), jadi:
          - nomor WA dinormalisasi ke 'core' signifikan (lihat phone_core)
          - kolom DB juga dibersihkan dari non-digit via regexp_replace
          - dicocokkan secara 'contains' agar tahan prefix maupun beberapa nomor
            yang digabung dalam satu kolom.

        Return: list toko yang cocok (0, 1, atau >1).
        """
        from app.core.phone import phone_core

        core = phone_core(wa_number)
        # Guard: core terlalu pendek berisiko false match — abaikan.
        if len(core) < 7:
            logger.info("toko_by_phone_skip", wa_number=wa_number, core=core)
            return []

        pool = await get_erp_pool()
        sql = """
            SELECT t.id, t.kodetoko, t.namatoko, t.alamat, t.kota, t.kecamatan,
                   t.propinsi, t.hp, t.telp, t.piutangb, t.plafon
            FROM mstr.toko t
            INNER JOIN (
                SELECT DISTINCT ON (tokoid) tokoid, statusaktif
                FROM mstr.tokoaktifpasif
                ORDER BY tokoid, tglstatus DESC
            ) tap ON t.id = tap.tokoid
            WHERE tap.statusaktif = true
              AND (
                    regexp_replace(COALESCE(t.hp, ''),   '[^0-9]', '', 'g') LIKE '%' || $1 || '%'
                 OR regexp_replace(COALESCE(t.telp, ''), '[^0-9]', '', 'g') LIKE '%' || $1 || '%'
              )
            ORDER BY t.namatoko
            LIMIT 10;
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, core)

        logger.info("toko_by_phone", core=core, matches=len(rows))
        return [
            {
                "toko_id": str(row["id"]),
                "kode": row["kodetoko"],
                "name": row["namatoko"],
                "address": ", ".join(filter(None, [
                    row["alamat"], row["kota"], row["kecamatan"]
                ])),
                "phone": row["hp"] or row["telp"],
                "piutang": float(row["piutangb"] or 0),
                "plafon": float(row["plafon"] or 0),
            }
            for row in rows
        ]

    # ── PRODUK ───────────────────────────────────────────────────

    async def get_products(self, active_only: bool = True) -> list[dict]:
        """
        Ambil semua produk dari mstr.stock.
        Dipakai untuk pencarian produk atau keperluan sync master data.
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
        """Cari spare part — tiap kata di-AND agar nama barang panjang tetap cocok."""
        cols = [
            "namabarang", "kodebarang", "brandproduct",
            "merkkendaraan", "typekendaraan", "kendaraan", "partno", "kategori",
        ]

        # Pecah query per kata, abaikan kata < 2 huruf
        keywords = [w.strip() for w in query.split() if len(w.strip()) >= 2]
        if not keywords:
            keywords = [query]

        # Bangun kondisi: setiap kata harus ada di salah satu kolom (OR antar kolom, AND antar kata)
        and_blocks = []
        params: list = []
        idx = 1
        for kw in keywords:
            or_parts = []
            for col in cols:
                or_parts.append(f"{col} ILIKE ${idx}")
                params.append(f"%{kw}%")
                idx += 1
            and_blocks.append(f"({' OR '.join(or_parts)})")

        where_clause = "\n  AND ".join(and_blocks)
        params.append(limit)

        sql = f"""SELECT id, kodebarang, namabarang, satuan,
       kategori, subkategori, brandproduct,
       merkkendaraan, typekendaraan, kendaraan,
       partno, groupstock
FROM mstr.stock
WHERE statusaktif = true
  AND kodebarang NOT ILIKE 'SB%'
  AND kodebarang NOT ILIKE 'SE%'
  AND {where_clause}
ORDER BY namabarang
LIMIT ${idx};"""

        # Versi human-readable untuk copy-paste ke pgAdmin
        sql_debug = sql
        for i, p in enumerate(params[:-1], 1):
            sql_debug = sql_debug.replace(f"${i}", f"'{p}'", 1)
        sql_debug = sql_debug.replace(f"${idx}", str(limit), 1)

        print("\n" + "="*60)
        print("🔍 [DEBUG search_products — COPY PASTE KE PGADMIN]")
        print("="*60)
        print(sql_debug)
        print("="*60 + "\n")

        pool = await get_erp_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
        print(f"📊 [search_products RESULT]: {len(rows)} baris ditemukan\n")

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

    async def _get_serving_subcabang_ids(self, toko_id: str) -> list:
        """
        Tentukan subcabang mana yang melayani propinsi toko yang order.

        Alur (lintas 2 database):
          1. [wiser/Server 1] baca `mstr.toko.propinsi` (nama propinsi) toko ini,
             cari `id` propinsi-nya di `mstr.provinsi` (match ILIKE by namaprovinsi).
          2. [wiserdc/Server 2] cari `mstr.subcabang.id` yang propinsi-id tsb ADA di
             kolom CSV `provinsiidmapping` (mis. "23,7,15,30"). 1 propinsi bisa
             dilayani >1 subcabang → hasil bisa banyak.

        `mstr.subcabang.id` inilah yang == `recordownerid` di rekapstocktoday.
        Return: list subcabang id (kosong bila propinsi/subcabang tak ketemu).
        """
        try:
            toko_id_int = int(toko_id)
        except (TypeError, ValueError):
            logger.info("subcabang_resolve_skip", reason="toko_id invalid", toko_id=toko_id)
            return []

        # 1) Propinsi toko → daftar propinsi-id (wiser / Server 1)
        erp_pool = await get_erp_pool()
        async with erp_pool.acquire() as conn:
            prov_rows = await conn.fetch(
                """
                SELECT DISTINCT b.id
                FROM mstr.toko a
                JOIN mstr.provinsi b ON a.propinsi ILIKE b.namaprovinsi
                WHERE a.id = $1
                """,
                toko_id_int,
            )
        provinsi_ids = [str(r["id"]) for r in prov_rows if r["id"] is not None]
        if not provinsi_ids:
            logger.info("subcabang_resolve_empty", stage="provinsi", toko_id=toko_id)
            return []

        # 2) Subcabang yang cover salah satu propinsi-id (wiserdc / Server 2)
        #    provinsiidmapping = CSV "23,7,15,30" → split & cek overlap dengan
        #    daftar propinsi-id toko (spasi dibersihkan agar "23, 7" tetap cocok).
        batch_pool = await get_batch_pool()
        async with batch_pool.acquire() as conn:
            sub_rows = await conn.fetch(
                """
                SELECT id
                FROM mstr.subcabang
                WHERE provinsiidmapping IS NOT NULL
                  AND provinsiidmapping <> ''
                  AND string_to_array(
                          regexp_replace(provinsiidmapping, '\\s', '', 'g'), ','
                      ) && $1::text[]
                """,
                provinsi_ids,
            )
        subcabang_ids = [r["id"] for r in sub_rows if r["id"] is not None]
        logger.info(
            "subcabang_resolved",
            toko_id=toko_id,
            provinsi_ids=provinsi_ids,
            subcabang_count=len(subcabang_ids),
        )
        return subcabang_ids

    async def _sum_stock(self, stock_id: int, recordowner_ids: list) -> dict:
        """
        SUM stok barang `stock_id` hanya untuk gudang (recordownerid) yang
        melayani propinsi toko. Ambil snapshot TERBARU per recordownerid dulu
        (tiap gudang punya tanggal update sendiri), baru dijumlahkan.
        """
        if not recordowner_ids:
            return {"qty": 0, "last_updated": "-"}

        batch_pool = await get_batch_pool()
        async with batch_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT SUM(latest.stokakhir) AS total_stok,
                       MAX(latest.tanggal)   AS last_updated
                FROM (
                    SELECT DISTINCT ON (recordownerid)
                           recordownerid, stokakhir, tanggal
                    FROM batch.rekapstocktoday
                    WHERE stockid = $1
                      AND recordownerid = ANY($2)
                    ORDER BY recordownerid, tanggal DESC
                ) AS latest
                """,
                stock_id,
                recordowner_ids,
            )
        qty = int(row["total_stok"] or 0) if row else 0
        last_updated = str(row["last_updated"]) if row and row["last_updated"] else "-"
        return {"qty": qty, "last_updated": last_updated}

    async def get_stock(self, product_code: str, toko_id: str) -> dict:
        """
        Cek stok on-hand barang untuk toko tertentu.

        Stok tidak lagi "semua gudang", melainkan hanya gudang (subcabang) yang
        melayani propinsi toko yang order. Alur:
          1. [wiser/Server 1] kodebarang → stock_id (mstr.stock).
          2. resolusi subcabang yang melayani propinsi toko (_get_serving_subcabang_ids).
          3. [wiserdc/Server 2] SUM stok terbaru per subcabang tsb.
        Fallback: propinsi/subcabang tak ketemu → stok 0.
        """
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
                "warehouse": "Cabang Toko",
            }

        stock_id = stock_row["id"]
        subcabang_ids = await self._get_serving_subcabang_ids(toko_id)
        res = await self._sum_stock(stock_id, subcabang_ids)

        return {
            "product_code": product_code,
            "stock_id": stock_id,
            "product_name": stock_row["namabarang"],
            "qty_available": res["qty"],
            "uom": stock_row["satuan"] or "pcs",
            "warehouse": "Cabang Toko",
            "last_updated": res["last_updated"],
        }

    async def get_stock_by_id(self, stock_id: int, toko_id: str) -> dict:
        """
        Cek stok harian by stock_id, toko-scoped.

        Sama seperti get_stock: hanya gudang (subcabang) yang melayani propinsi
        toko yang order. Fallback subcabang kosong → stok 0.
        """
        subcabang_ids = await self._get_serving_subcabang_ids(toko_id)
        res = await self._sum_stock(stock_id, subcabang_ids)
        return {
            "stock_id": stock_id,
            "qty_available": res["qty"],
            "warehouse": "Cabang Toko",
            "last_updated": res["last_updated"],
        }

    # ── SALES ORDER ──────────────────────────────────────────────

    async def get_toko_order_attrs(self, toko_id: str) -> dict | None:
        """
        Ambil atribut toko yang dibutuhkan untuk push order ke Wiser:
        tokoidwarisan (untuk tokoidsas) dan jangkawaktukredit (tempo/tipe transaksi).
        """
        pool = await get_erp_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, kodetoko, namatoko, tokoidwarisan, jangkawaktukredit
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
            "tokoidwarisan": row["tokoidwarisan"],
            "jangkawaktukredit": int(row["jangkawaktukredit"] or 0),
        }

    async def create_sales_order(self, payload: dict) -> dict:
        """
        Push final order ke Wiser (tos.orderpembelian via tambahapi).
        Mengembalikan: {status, so_number, wisertosopid, errormessage}
        status: "success" | "duplicate" | "error"
        """
        from .wiser import submit_order_to_wiser

        toko_id = payload.get("toko_id", "")
        lines = payload.get("lines", [])
        note = payload.get("note") or None
        draft_order_id = payload.get("draft_order_id")

        logger.info("create_so_requested", toko_id=toko_id, item_count=len(lines))

        # Resolusi atribut toko (tokoidwarisan wajib untuk Wiser).
        attrs = await self.get_toko_order_attrs(toko_id)
        if not attrs or not attrs.get("tokoidwarisan"):
            return {
                "status": "error",
                "so_number": None,
                "wisertosopid": None,
                "errormessage": (
                    f"Toko ID {toko_id} tidak ditemukan atau tidak punya "
                    "tokoidwarisan; order tidak bisa dikirim ke ERP."
                ),
            }

        return await submit_order_to_wiser(
            toko_id=toko_id,
            tokoidwarisan=attrs["tokoidwarisan"],
            jangkawaktukredit=attrs["jangkawaktukredit"],
            items=lines,
            note=note,
            draft_order_id=draft_order_id,
        )

    # ── AR / PIUTANG ─────────────────────────────────────────────

    async def get_customer_ar(self, toko_id: str) -> dict:
        """Ambil info sisa plafon dan piutang berjalan toko."""
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


# Daftarkan semua komponen publik package agar bisa diimport dengan ringkas
__all__ = [
    "get_erp_pool",
    "get_batch_pool",
    "ERPClient",
    "find_toko_hybrid"
]