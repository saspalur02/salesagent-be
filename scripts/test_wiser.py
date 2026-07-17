"""
Test Wiser push (Order Pembelian tambahapi).

Pemakaian:
  python -m scripts.test_wiser build        # rakit & cetak payload (tanpa kirim)
  python -m scripts.test_wiser send-sample  # KIRIM payload contoh dari MD ke Wiser
  python -m scripts.test_wiser submit <toko_id> <kodebarang> <qty> <harga>
                                            # alur penuh: nomor AISO + builder + kirim

⚠️ 'send-sample' & 'submit' BENAR-BENAR memanggil endpoint produksi Wiser.
"""
import asyncio
import json
import sys

from app.services.erp.wiser import (
    WiserClient,
    _build_payload,
    submit_order_to_wiser,
)


def _print(title, obj):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)
    print(json.dumps(obj, indent=2, ensure_ascii=False))


async def cmd_build():
    """Rakit payload dari order dummy (tanpa DB / tanpa kirim)."""
    payload = _build_payload(
        noso="AISO/2606/00001",
        externalid=999001,
        tokoidwarisan="1045764",
        jangkawaktukredit=90,
        items=[
            {"product_code": "FE4NAPF077UA", "qty": 38, "price": 152000},
            {"product_code": "FB4TSS2032YE", "qty": 2, "price": 99900},
        ],
        note=None,
    )
    _print("PAYLOAD (dry-run)", payload)


async def cmd_send_sample():
    """Kirim payload contoh persis dari dokumen MD."""
    from app.core.settings import get_settings
    s = get_settings()
    payload = {
        "apikey": s.wiser_api_key,
        "omsetsubcabangid": "0901",
        "tasksalesid": 298994,
        "tasksalesnoso": "AISO/2606/09999",
        "tasksalestglso": "20260625",
        "tokoidsas": "1045764|248",
        "temponotabe": "90",
        "temponotanonbe": "0",
        "tipetransaksi": "K",
        "statuspembayaran": "KREDIT",
        "kodesales": "AI-BOT",
        "tasksalescreatedby": "AI-BOT",
        "tasksalescreatedon": "20260625",
        "tasksalesupdatedby": "AI-BOT",
        "tasksalesupdatedon": "20260625",
        "tasksalestokostatusbmk": "AGEN",
        "tasksalescurrency": "IDR",
        "keterangan": None,
        "tasksalessotype": "TSSO",
        "flgordersalesman": "Y",
        "redeempoint": 0,
        "tasksalessodetail": [
            {
                "takssalesdetailid": "29899401",
                "kodebarangsas": "FE4NAPF077UA",
                "qtyorder": "38",
                "hargasatuanbmk": "152000",
                "hargasatuanajuan": "152000",
                "hargaitembeforetax": "5776000",
                "hargaitemtax": "0",
                "hargaitemaftertax": "5776000",
                "tasksalesketerangan": None,
                "flg_inden_so": "N",
            }
        ],
    }
    _print("MENGIRIM PAYLOAD CONTOH", payload)
    resp = await WiserClient().kirim_order_pembelian(payload)
    _print("RESPONSE", resp)


async def cmd_submit(toko_id, kodebarang, qty, harga):
    """Alur penuh: generate AISO + builder + kirim (butuh DB lokal + tokoidwarisan)."""
    from app.services.erp import ERPClient
    erp = ERPClient()
    attrs = await erp.get_toko_order_attrs(toko_id)
    _print("TOKO ATTRS", attrs)
    if not attrs or not attrs.get("tokoidwarisan"):
        print("Toko tidak punya tokoidwarisan — batal.")
        return
    result = await submit_order_to_wiser(
        toko_id=toko_id,
        tokoidwarisan=attrs["tokoidwarisan"],
        jangkawaktukredit=attrs["jangkawaktukredit"],
        items=[{"product_code": kodebarang, "qty": float(qty), "price": float(harga)}],
        note="Test submit via scripts/test_wiser.py",
    )
    _print("RESULT", result)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "build":
        asyncio.run(cmd_build())
    elif cmd == "send-sample":
        asyncio.run(cmd_send_sample())
    elif cmd == "submit":
        asyncio.run(cmd_submit(*sys.argv[2:6]))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
