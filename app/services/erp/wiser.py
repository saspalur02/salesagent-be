"""
Wiser / Custom ERP client — push final order ke endpoint Order Pembelian `tambahapi`.

Kontrak API: tests/API-OrderPembelian-Tambah.md
Alur:
  1. Generate nomor SO (AISO/YYMM/NNNNN) + externalid via tabel lokal (atomik).
  2. Rakit payload sesuai kontrak (harga sudah termasuk PPN 11% → pisah pajak).
  3. POST ke Wiser, perlakukan sukses HANYA bila response status == "success".
  4. Simpan audit + status ke tabel wiser_order (idempotensi).
"""
import json
from datetime import datetime, timezone

import httpx
from sqlalchemy import select, text
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.settings import get_settings
from app.core.logging import get_logger
from app.db.database import AsyncSessionLocal
from app.models.wiser_order import AisoCounter, WiserOrder

settings = get_settings()
logger = get_logger(__name__)


# ── HTTP client ──────────────────────────────────────────────────

class WiserClient:
    """POST final order ke Wiser `tambahapi`."""

    def __init__(self):
        self.url = settings.wiser_api_url
        self.timeout = settings.wiser_timeout

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type(httpx.HTTPError),
        reraise=True,
    )
    async def kirim_order_pembelian(self, payload: dict) -> dict:
        """
        Kirim payload ke Wiser. Retry hanya untuk error jaringan
        (aman karena Wiser menolak duplikat noso/externalid).
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                self.url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            return resp.json()


# ── Helper: penomoran AISO (atomik per-periode) ──────────────────

async def _next_noso(session) -> tuple[str, str]:
    """
    Hasilkan (noso, periode) format AISO/YYMM/NNNNN dengan row-lock
    agar tidak ada nomor kembar saat concurrent.
    """
    periode = datetime.now(timezone.utc).strftime("%y%m")

    # Pastikan baris periode ada, lalu kunci & increment.
    await session.execute(
        text(
            "INSERT INTO aiso_counter (periode, last_seq) VALUES (:p, 0) "
            "ON CONFLICT (periode) DO NOTHING"
        ),
        {"p": periode},
    )
    row = (
        await session.execute(
            select(AisoCounter).where(AisoCounter.periode == periode).with_for_update()
        )
    ).scalar_one()
    row.last_seq += 1
    seq = row.last_seq
    noso = f"AISO/{periode}/{seq:05d}"
    return noso, periode


# ── Helper: hitung komponen harga (input sudah termasuk PPN) ─────

def _hitung_harga_item(unit_incl: float, qty: float) -> dict:
    """
    `unit_incl` = harga satuan yang diinput admin (SUDAH termasuk PPN).
    beforetax = aftertax / (1 + ppn); tax = aftertax - beforetax.
    """
    ppn = settings.wiser_ppn_rate
    after = round(unit_incl * qty)
    before = round(after / (1 + ppn))
    tax = after - before
    return {
        "hargasatuanbmk": str(round(unit_incl)),
        "hargasatuanajuan": str(round(unit_incl)),
        "hargaitembeforetax": str(before),
        "hargaitemtax": str(tax),
        "hargaitemaftertax": str(after),
    }


# ── Builder payload ──────────────────────────────────────────────

def _build_payload(
    *,
    noso: str,
    externalid: int,
    tokoidwarisan: str,
    jangkawaktukredit: int,
    items: list[dict],
    note: str | None,
) -> dict:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    kodesales = settings.wiser_kodesales

    # Tempo & tipe transaksi dari jangka waktu kredit toko.
    tempo = int(jangkawaktukredit or 0)
    if tempo > 0:
        tipetransaksi = "K"
        statuspembayaran = "KREDIT"
    else:
        tipetransaksi = "T"
        statuspembayaran = "TUNAI"

    detail = []
    for i, it in enumerate(items, 1):
        qty = float(it.get("qty") or 0)
        unit = float(it.get("price") or 0)
        harga = _hitung_harga_item(unit, qty)
        detail.append({
            "takssalesdetailid": f"{externalid}{i:03d}",  # unik per sotype
            "kodebarangsas": it.get("product_code", ""),
            "qtyorder": str(int(qty)) if qty == int(qty) else str(qty),
            "tasksalesketerangan": it.get("note"),
            "flg_inden_so": "N",
            **harga,
        })

    payload = {
        "apikey": settings.wiser_api_key,
        "tasksalesid": externalid,
        "tasksalesnoso": noso,
        "tasksalestglso": today,
        "tokoidsas": str(tokoidwarisan),
        "temponotabe": str(tempo),
        "temponotanonbe": "0",
        "tipetransaksi": tipetransaksi,
        "statuspembayaran": statuspembayaran,
        "kodesales": kodesales,
        "tasksalescreatedby": kodesales,
        "tasksalescreatedon": today,
        "tasksalesupdatedby": kodesales,
        "tasksalesupdatedon": today,
        "tasksalestokostatusbmk": settings.wiser_status_bmk,
        "tasksalescurrency": settings.wiser_currency,
        "keterangan": note,
        "tasksalessotype": settings.wiser_sotype,
        "flgordersalesman": "Y",
        "redeempoint": 0,
        "tasksalessodetail": detail,
    }
    return payload


# ── Orchestrator: generate nomor → kirim → audit ─────────────────

async def submit_order_to_wiser(
    *,
    toko_id: str,
    tokoidwarisan: str,
    jangkawaktukredit: int,
    items: list[dict],
    note: str | None = None,
    draft_order_id: int | None = None,
) -> dict:
    """
    Kirim final order ke Wiser. Kembalikan dict:
      {status, so_number, wisertosopid, errormessage}
    status: "success" | "duplicate" | "error"
    """
    sotype = settings.wiser_sotype

    # 1) Generate nomor + simpan baris audit (commit dulu supaya nomor tak terpakai ulang).
    async with AsyncSessionLocal() as session:
        async with session.begin():
            noso, _ = await _next_noso(session)
            order_row = WiserOrder(
                noso=noso,
                sotype=sotype,
                toko_id=str(toko_id),
                tokoidwarisan=str(tokoidwarisan),
                draft_order_id=draft_order_id,
                status="pending",
            )
            session.add(order_row)
            await session.flush()  # dapatkan externalid (PK autoincrement)
            externalid = order_row.externalid

            payload = _build_payload(
                noso=noso,
                externalid=externalid,
                tokoidwarisan=tokoidwarisan,
                jangkawaktukredit=jangkawaktukredit,
                items=items,
                note=note,
            )
            order_row.payload = json.dumps(payload, ensure_ascii=False)
        # transaksi commit di sini → nomor & baris persist

    logger.info("wiser_submit_start", noso=noso, externalid=externalid, items=len(items))

    # 2) Kirim ke Wiser.
    result = {"status": "error", "so_number": noso, "wisertosopid": None, "errormessage": None}
    try:
        resp = await WiserClient().kirim_order_pembelian(payload)
    except Exception as e:
        result["errormessage"] = f"Gagal menghubungi Wiser: {e}"
        await _update_order(externalid, status="failed", errormessage=result["errormessage"])
        logger.error("wiser_submit_network_error", noso=noso, error=str(e))
        return result

    # 3) Interpretasi response (sukses HANYA bila status == "success").
    status_field = resp.get("status")
    errmsg = resp.get("errormessage") or resp.get("message") or ""

    if status_field == "success":
        result.update(
            status="success",
            wisertosopid=resp.get("wisertosopid"),
            errormessage=resp.get("errormessage"),
        )
        await _update_order(
            externalid, status="success",
            wisertosopid=resp.get("wisertosopid"),
            response=resp,
        )
        logger.info("wiser_submit_success", noso=noso, wisertosopid=resp.get("wisertosopid"))
    elif "sudah ada" in errmsg.lower():
        result.update(status="duplicate", errormessage=errmsg)
        await _update_order(externalid, status="failed", errormessage=errmsg, response=resp)
        logger.warning("wiser_submit_duplicate", noso=noso, msg=errmsg)
    else:
        result.update(status="error", errormessage=errmsg or str(resp))
        await _update_order(externalid, status="failed", errormessage=result["errormessage"], response=resp)
        logger.error("wiser_submit_business_error", noso=noso, msg=result["errormessage"])

    return result


async def _update_order(externalid: int, **fields) -> None:
    """Update baris audit wiser_order."""
    resp = fields.pop("response", None)
    if resp is not None:
        fields["response"] = json.dumps(resp, ensure_ascii=False)
    async with AsyncSessionLocal() as session:
        async with session.begin():
            row = await session.get(WiserOrder, externalid)
            if row:
                for k, v in fields.items():
                    setattr(row, k, v)
