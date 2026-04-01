"""
Test koneksi dan query ke ERP database.
Jalankan: python scripts/test_erp.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from app.services.erp import ERPClient, get_erp_pool, get_batch_pool


async def test_koneksi():
    print("\n[1] Test koneksi ERP Server 1 (mstr.toko + mstr.stock)...")
    try:
        pool = await get_erp_pool()
        async with pool.acquire() as conn:
            result = await conn.fetchval("SELECT version()")
            print(f"OK: {result[:50]}...")
    except Exception as e:
        print(f"GAGAL: {e}")
        return False
    return True


async def test_koneksi_batch():
    print("\n[2] Test koneksi ERP Server 2 (batch.rekapstocktoday)...")
    try:
        pool = await get_batch_pool()
        async with pool.acquire() as conn:
            result = await conn.fetchval("SELECT version()")
            print(f"OK: {result[:50]}...")
    except Exception as e:
        print(f"GAGAL: {e}")
        return False
    return True


async def test_toko():
    print("\n[3] Test query mstr.toko...")
    try:
        pool = await get_erp_pool()
        async with pool.acquire() as conn:
            # Ambil 3 toko pertama
            rows = await conn.fetch(
                """
                SELECT id, kodetoko, namatoko, kota, hp, statusaktif
                FROM mstr.toko
                WHERE statusaktif = true
                ORDER BY namatoko
                LIMIT 3
                """
            )
        print(f"OK: Ditemukan {len(rows)} toko (sample):")
        for r in rows:
            print(f"  - [{r['kodetoko']}] {r['namatoko']} | {r['kota']} | HP: {r['hp']}")
    except Exception as e:
        print(f"GAGAL: {e}")


async def test_produk():
    print("\n[4] Test query mstr.stock...")
    try:
        pool = await get_erp_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, kodebarang, namabarang, satuan, kategori, brandproduct
                FROM mstr.stock
                WHERE statusaktif = true
                ORDER BY namabarang
                LIMIT 3
                """
            )
        print(f"OK: Ditemukan {len(rows)} produk (sample):")
        for r in rows:
            print(f"  - [{r['kodebarang']}] {r['namabarang']} | {r['satuan']} | {r['kategori']}")
    except Exception as e:
        print(f"GAGAL: {e}")


async def test_stok():
    print("\n[5] Test query batch.rekapstocktoday...")
    try:
        pool = await get_batch_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT stockid, stokakhir, stokgudang, tanggal
                FROM batch.rekapstocktoday
                ORDER BY tanggal DESC
                LIMIT 3
                """
            )
        print(f"OK: Ditemukan {len(rows)} record stok (sample):")
        for r in rows:
            print(f"  - StockID: {r['stockid']} | Stok: {r['stokakhir']} | Tanggal: {r['tanggal']}")
    except Exception as e:
        print(f"GAGAL: {e}")


async def test_search_toko():
    print("\n[6] Test cari_toko (ERPClient)...")
    try:
        erp = ERPClient()
        # Ganti dengan nama toko yang ada di database kamu
        results = await erp.find_toko("toko", "")
        print(f"OK: Ditemukan {len(results)} toko:")
        for t in results[:3]:
            print(f"  - [{t['toko_id']}] {t['name']} | {t['address']}")
    except Exception as e:
        print(f"GAGAL: {e}")


async def test_search_produk():
    print("\n[7] Test search_products (ERPClient)...")
    try:
        erp = ERPClient()
        # Ganti dengan nama produk yang ada di database kamu
        results = await erp.search_products("a", limit=3)
        print(f"OK: Ditemukan {len(results)} produk:")
        for p in results:
            print(f"  - [{p['code']}] {p['name']} | {p['uom']}")
    except Exception as e:
        print(f"GAGAL: {e}")


async def main():
    print("=" * 55)
    print("  ERP Database Connection Test")
    print("=" * 55)

    from app.core.settings import get_settings
    s = get_settings()
    print(f"\nERP DB 1 : {s.erp_db_url[:40]}..." if s.erp_db_url else "\nERP DB 1 : BELUM DISET!")
    print(f"ERP DB 2 : {s.erp_batch_db_url[:40]}..." if s.erp_batch_db_url else "ERP DB 2 : BELUM DISET!")

    ok1 = await test_koneksi()
    ok2 = await test_koneksi_batch()

    if ok1:
        await test_toko()
        await test_produk()
        await test_search_toko()
        await test_search_produk()

    if ok2:
        await test_stok()

    print("\n" + "=" * 55)
    print("Test selesai!")


if __name__ == "__main__":
    asyncio.run(main())
