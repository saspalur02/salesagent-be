"""
Query toko dari ERP menggunakan hybrid search:
1. ILIKE nama toko + kata-kata alamat (primary)
2. ILIKE nama toko saja (fallback jika alamat tidak match)
"""
from app.core.logging import get_logger
from app.services.erp import get_erp_pool

logger = get_logger(__name__)


async def find_toko_hybrid(nama_toko: str, alamat: str = "") -> list[dict]:
    """
    Cari toko dengan hybrid approach:
    - Nama toko: ILIKE (exact-ish match)
    - Alamat: split kata, OR ILIKE per kata
    
    Return list toko yang match.
    """
    pool = await get_erp_pool()
    
    # Bersihkan input
    nama_toko = nama_toko.strip()
    alamat_words = [
        w for w in alamat.lower().split()
        if len(w) > 3  # abaikan kata pendek (di, di, ke, dll)
        and w not in {"yang", "toko", "dari", "motor", "jalan", "jl"}
    ]

    async with pool.acquire() as conn:

        # ── Step 1: Cari dengan nama + alamat ───────────────────
        if alamat_words:
            # Bangun kondisi OR untuk setiap kata alamat
            alamat_conditions = " OR ".join([
                f"""(
                    alamat ILIKE '%{w}%' OR
                    kota ILIKE '%{w}%' OR
                    kecamatan ILIKE '%{w}%' OR
                    propinsi ILIKE '%{w}%'
                )"""
                for w in alamat_words
            ])

            rows = await conn.fetch(
                f"""
                SELECT id, kodetoko, namatoko, alamat, kota,
                       kecamatan, propinsi, hp, piutangb, plafon
                FROM mstr.toko
                WHERE statusaktif = true
                  AND namatoko ILIKE $1
                  AND ({alamat_conditions})
                ORDER BY namatoko
                LIMIT 10
                """,
                f"%{nama_toko}%",
            )

            if rows:
                logger.info("toko_found_with_alamat",
                           nama=nama_toko, alamat=alamat, count=len(rows))
                return _format_rows(rows)

        # ── Step 2: Fallback — nama saja ────────────────────────
        rows = await conn.fetch(
            """
            SELECT id, kodetoko, namatoko, alamat, kota,
                   kecamatan, propinsi, hp, piutangb, plafon
            FROM mstr.toko
            WHERE statusaktif = true
              AND namatoko ILIKE $1
            ORDER BY namatoko
            LIMIT 20
            """,
            f"%{nama_toko}%",
        )

        logger.info("toko_found_name_only",
                   nama=nama_toko, count=len(rows))
        return _format_rows(rows)


def _format_rows(rows) -> list[dict]:
    return [
        {
            "toko_id": str(row["id"]),
            "kode": row["kodetoko"],
            "name": row["namatoko"],
            "address": ", ".join(filter(None, [
                row["alamat"], row["kota"], row["kecamatan"]
            ])),
            "phone": row["hp"],
            "piutang": float(row["piutangb"] or 0),
            "plafon": float(row["plafon"] or 0),
        }
        for row in rows
    ]
