"""
Script untuk sync data toko + produk dari ERP ke pgvector.
Jalankan sekali untuk initial load, lalu berkala (misal tiap malam).

Jalankan: python scripts/sync_embeddings.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from app.services.vector import setup_tables, upsert_toko, upsert_produk
from app.services.erp import get_erp_pool


async def sync_toko():
    print("\n[1] Sync data toko dari mstr.toko ke pgvector...")
    pool = await get_erp_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, kodetoko, namatoko, alamat, kota, kecamatan,
                   propinsi, hp, piutangb, plafon, statusaktif
            FROM mstr.toko
            WHERE statusaktif = true
            ORDER BY id
            """
        )

    total = len(rows)
    print(f"Total toko aktif: {total}")

    success = 0
    failed = 0
    batch_size = 50

    for i, row in enumerate(rows):
        try:
            await upsert_toko(dict(row))
            success += 1
        except Exception as e:
            failed += 1
            print(f"  ERROR toko {row['id']} {row['namatoko']}: {e}")

        # Progress setiap 50 toko
        if (i + 1) % batch_size == 0 or (i + 1) == total:
            pct = round((i + 1) / total * 100)
            print(f"  Progress: {i+1}/{total} ({pct}%) | OK: {success} | Gagal: {failed}")

    print(f"Selesai sync toko: {success} berhasil, {failed} gagal")
    return success


async def sync_produk():
    print("\n[2] Sync data produk dari mstr.stock ke pgvector...")
    pool = await get_erp_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, kodebarang, namabarang, satuan, kategori,
                   subkategori, brandproduct, merkkendaraan,
                   typekendaraan, kendaraan, partno, groupstock
            FROM mstr.stock
            WHERE statusaktif = true
            ORDER BY id
            """
        )

    total = len(rows)
    print(f"Total produk aktif: {total}")

    success = 0
    failed = 0
    batch_size = 100

    for i, row in enumerate(rows):
        try:
            await upsert_produk(dict(row))
            success += 1
        except Exception as e:
            failed += 1
            if failed <= 5:  # Tampilkan max 5 error
                print(f"  ERROR produk {row['id']} {row['namabarang']}: {e}")

        # Progress setiap 100 produk
        if (i + 1) % batch_size == 0 or (i + 1) == total:
            pct = round((i + 1) / total * 100)
            print(f"  Progress: {i+1}/{total} ({pct}%) | OK: {success} | Gagal: {failed}")

    print(f"Selesai sync produk: {success} berhasil, {failed} gagal")
    return success


async def main():
    print("=" * 55)
    print("  Sync ERP → pgvector (Embedding)")
    print("=" * 55)

    from app.core.settings import get_settings
    s = get_settings()
    print(f"\nVector DB : {s.pgvector_url[:40]}...")

    # Setup tabel dulu
    print("\n[0] Setup tabel vector store...")
    await setup_tables()
    print("OK: Tabel siap!")

    import time
    start = time.time()

    # Sync toko
    toko_count = await sync_toko()

    # Sync produk
    produk_count = await sync_produk()

    elapsed = round(time.time() - start)
    print(f"\n{'='*55}")
    print(f"Sync selesai dalam {elapsed} detik!")
    print(f"Total: {toko_count} toko + {produk_count} produk di-embed")
    print(f"{'='*55}")


if __name__ == "__main__":
    asyncio.run(main())
