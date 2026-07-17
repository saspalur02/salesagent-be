import asyncio
import sys
import os
import argparse
import time

# Pastikan path 'app' terbaca di paling awal
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.services.vector import (
    upsert_toko, 
    upsert_produk, 
    get_table_toko, 
    get_table_produk, 
    get_vector_pool,
    setup_tables
)
from app.services.erp import get_erp_pool
from app.core.settings import get_settings
import app.services.vector as vs

async def sync_toko():
    s = get_settings()
    table_name = get_table_toko()
    
    # 1. Cek ID yang sudah ada di Database Vector (.221)
    v_pool = await get_vector_pool()
    async with v_pool.acquire() as v_conn:
        print(f"[TOKO] Mengecek data yang sudah ada di {table_name}...")
        existing_rows = await v_conn.fetch(f"SELECT toko_id FROM {table_name}")
        # Paksa convert ke string untuk menghindari bug beda tipe data (int vs str)
        done_ids = {str(r['toko_id']) for r in existing_rows}

    # 2. Ambil data dari Database ERP (.26)
    e_pool = await get_erp_pool()
    async with e_pool.acquire() as e_conn:
        
        # KITA KUNCI STRUKTUR QUERY-NYA DISINI
        query_bersih = """
            SELECT t.id, t.kodetoko, t.namatoko, t.alamat, t.kota, t.kecamatan,
                   t.propinsi, t.hp, t.piutangb, t.plafon
            FROM mstr.toko t
            INNER JOIN (
                SELECT DISTINCT ON (tokoid) tokoid, statusaktif 
                FROM mstr.tokoaktifpasif 
                ORDER BY tokoid, tglstatus DESC
            ) tap ON t.id = tap.tokoid
            WHERE tap.statusaktif = true
            ORDER BY t.id ASC;
        """
        
        # ─── PROSES CETAK QUERY KE TERMINAL VS CODE ───
        print("\n========================================================")
        print("🔥 RUNNING SQL QUERY KE ERP (.26) 🔥")
        print("========================================================")
        print(query_bersih.strip())
        print("========================================================\n")
        
        rows = await e_conn.fetch(query_bersih)
        print(f"📊 [DATABASE ERP RETURN]: Berhasil menarik {len(rows)} baris data dari ERP.")

    # 3. Filter: Ambil yang BELUM ADA di Vector DB
    to_process = [row for row in rows if str(row['id']) not in done_ids]
    total = len(to_process)

    if total == 0:
        print("[TOKO] Semua data toko sudah sinkron.")
        return 0

    print(f"[TOKO] Memproses {total} data baru (Resume mode)...")

    success = 0
    failed = 0
    vs._current_provider = s.embedding_provider_toko

    for i, row in enumerate(to_process):
        try:
            await upsert_toko(dict(row))
            success += 1
        except Exception as e:
            failed += 1
            if failed <= 5: print(f"   ERROR Toko {row['id']}: {e}")

        if (i + 1) % 100 == 0 or (i + 1) == total:
            print(f"   Progress: {i+1}/{total} | OK: {success} | Gagal: {failed}")

    return success

async def sync_produk():
    s = get_settings()
    table_name = get_table_produk()
    
    # 1. Cek ID yang sudah ada di Database Vector (.221)
    v_pool = await get_vector_pool()
    async with v_pool.acquire() as v_conn:
        print(f"[PRODUK] Mengecek data yang sudah ada di {table_name}...")
        existing_rows = await v_conn.fetch(f"SELECT stock_id FROM {table_name}")
        done_ids = {r['stock_id'] for r in existing_rows}

    # 2. Ambil data dari Database ERP (.26)
    e_pool = await get_erp_pool()
    async with e_pool.acquire() as e_conn:
        rows = await e_conn.fetch(
            """
            SELECT id, kodebarang, namabarang, satuan, kategori,
                   subkategori, brandproduct, merkkendaraan,
                   typekendaraan, kendaraan, partno, groupstock
            FROM mstr.stock
            WHERE statusaktif = true
            ORDER BY id
            """
        )

    # 3. Filter: Hanya ambil yang ID-nya belum ada di Vector DB
    to_process = [row for row in rows if row['id'] not in done_ids]
    total = len(to_process)

    if total == 0:
        print("[PRODUK] Semua data produk sudah sinkron.")
        return 0

    print(f"[PRODUK] Memproses {total} data baru (Resume mode)...")

    success = 0
    failed = 0
    vs._current_provider = s.embedding_provider_produk

    for i, row in enumerate(to_process):
        try:
            await upsert_produk(dict(row))
            success += 1
        except Exception as e:
            failed += 1
            if failed <= 5: print(f"  ERROR Produk {row['id']}: {e}")

        if (i + 1) % 100 == 0 or (i + 1) == total:
            print(f"  Progress: {i+1}/{total} | OK: {success} | Gagal: {failed}")

    return success

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--toko", action="store_true")
    parser.add_argument("--produk", action="store_true")
    args = parser.parse_args()

    sync_all = not args.toko and not args.produk
    s = get_settings()

    print("=" * 60)
    print("  Sync ERP → pgvector (Multi-Server Resume Mode)")
    print("=" * 60)
    print(f"Toko Provider   : {s.embedding_provider_toko}")
    print(f"Produk Provider : {s.embedding_provider_produk}")

    # Pastikan tabel-tabel di server .221 sudah siap
    await setup_tables()

    start = time.time()
    t_count = p_count = 0

    if args.toko or sync_all:
        t_count = await sync_toko()
    if args.produk or sync_all:
        p_count = await sync_produk()

    print(f"\nSelesai dalam {round(time.time() - start)} detik.")
    if t_count: print(f"Toko   : {t_count} data baru")
    if p_count: print(f"Produk : {p_count} data baru")

if __name__ == "__main__":
    asyncio.run(main())