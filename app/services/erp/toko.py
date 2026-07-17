import structlog
from app.core.logging import get_logger
from .parser import parse_store_query_with_llm

logger = get_logger(__name__)

async def find_toko_hybrid(user_text: str) -> list[dict]:
    """
    Cari toko bertingkat dengan memisahkan nama toko dan alamat via LLM Parser:
    1. Coba cari dengan Nama Toko sebagai FRASA UTUH + Filter Alamat.
    2. Jika zonk, baru fallback ke metode lama (Nama Toko DI-PECAH PER KATA + Filter Alamat).
    """
    from . import get_erp_pool
    pool = await get_erp_pool()
    
    # ── PANGGIL PARSER DI AWAL SEBELUM TENTUIN STRATEGI ──
    parsed = await parse_store_query_with_llm(user_text)
    
    # Bersihkan nama toko murni hasil gabungan nama1 dan nama2 dari LLM
    nama_toko_utuh = f"{parsed.get('nama1', '')} {parsed.get('nama2', '')}".strip()
    
    print("\n" + "="*60)
    print("🔮 [DEBUG HYBRID TOKO - MEMBEDAKAN ENTITAS]")
    print("="*60)
    print(f"Input User      : '{user_text}'")
    print(f"Frasa Nama Toko : '{nama_toko_utuh}'")
    print(f"Kecamatan       : '{parsed.get('kecamatan', '')}'")
    print(f"Kota            : '{parsed.get('kota', '')}'")
    print(f"Alamat/Jl       : '{parsed.get('alamat', '')}'")
    print("="*60 + "\n")
    
    status_subquery = """
        (
            SELECT DISTINCT ON (tokoid) tokoid, statusaktif 
            FROM mstr.tokoaktifpasif 
            ORDER BY tokoid, tglstatus DESC
        ) tap
    """
    
    sql_base = f"""
        SELECT t.id, t.kodetoko, t.namatoko, t.alamat, t.kota,
               t.kecamatan, t.propinsi, t.hp, t.piutangb, t.plafon
        FROM mstr.toko t
        INNER JOIN {status_subquery} ON t.id = tap.tokoid
        WHERE tap.statusaktif = true
    """

    # ──────────────────────────────────────────────────────────
    # 🔥 STRATEGI 1: NAMA TOKO SEBAGAI FRASA UTUH + FILTER ALAMAT
    # ──────────────────────────────────────────────────────────
    if len(nama_toko_utuh) >= 2:
        print("[STRATEGI 1] Eksekusi pencarian dengan Frasa Nama Toko Utuh...")
        conditions_s1 = []
        params_s1 = []
        p_idx = 1
        
        # Kunci nama toko secara utuh (Phrase Match)
        conditions_s1.append(f"t.namatoko ILIKE ${p_idx}")
        params_s1.append(f"%{nama_toko_utuh}%")
        p_idx += 1
        
        # Ikut sertakan saringan alamat secara presisi jika diekstrak oleh LLM
        if parsed.get("alamat"):
            conditions_s1.append(f"t.alamat ILIKE ${p_idx}")
            params_s1.append(f"%{parsed['alamat']}%")
            p_idx += 1
        if parsed.get("kota"):
            conditions_s1.append(f"t.kota ILIKE ${p_idx}")
            params_s1.append(f"%{parsed['kota']}%")
            p_idx += 1
        if parsed.get("kecamatan"):
            conditions_s1.append(f"t.kecamatan ILIKE ${p_idx}")
            params_s1.append(f"%{parsed['kecamatan']}%")
            p_idx += 1
            
        sql_s1 = f"{sql_base} AND {' AND '.join(conditions_s1)} ORDER BY t.namatoko LIMIT 10;"
        
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql_s1, *params_s1)
            if rows:
                print(f"✅ [STRATEGI 1 MATCH]: Sukses nemu {len(rows)} toko pake frasa nama utuh!")
                return _format_rows(rows)

    # ──────────────────────────────────────────────────────────
    # 🍂 STRATEGI 2: FALLBACK — JIKA S1 ZONK, NAMA TOKO DI-PECAH KATA
    # ──────────────────────────────────────────────────────────
    print("⚠️ [STRATEGI 1 ZONK]: Masuk Strategi 2 (Pecah Kata Nama Toko)...")
    
    conditions_s2 = []
    params_s2 = []
    p_idx = 1
    
    # Pecah frasa nama toko menjadi potongan kata kunci tunggal
    nama_keywords = [w for w in nama_toko_utuh.split() if len(w) >= 2]
    for kw in nama_keywords:
        conditions_s2.append(f"t.namatoko ILIKE ${p_idx}")
        params_s2.append(f"%{kw}%")
        p_idx += 1
        
    if parsed.get("alamat"):
        conditions_s2.append(f"t.alamat ILIKE ${p_idx}")
        params_s2.append(f"%{parsed['alamat']}%")
        p_idx += 1
        
    if parsed.get("kota"):
        conditions_s2.append(f"t.kota ILIKE ${p_idx}")
        params_s2.append(f"%{parsed['kota']}%")
        p_idx += 1
        
    if parsed.get("kecamatan"):
        conditions_s2.append(f"t.kecamatan ILIKE ${p_idx}")
        params_s2.append(f"%{parsed['kecamatan']}%")
        p_idx += 1

    if not conditions_s2:
        conditions_s2.append(f"t.namatoko ILIKE $1")
        params_s2.append(f"%{user_text}%")

    sql_s2 = f"{sql_base} AND {' AND '.join(conditions_s2)} ORDER BY t.namatoko LIMIT 10;"

    async with pool.acquire() as conn:
        rows = await conn.fetch(sql_s2, *params_s2)
        print(f"📊 [STRATEGI 2 RESULT]: Menemukan {len(rows)} baris toko setelah dipecah.")
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