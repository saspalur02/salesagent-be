"""
Script untuk test kirim pesan WhatsApp via WAHA.
Jalankan dari root folder project:

    python scripts/test_wa.py

Pastikan .env sudah diisi:
    WAHA_BASE_URL=http://localhost:3000
    WAHA_SESSION=default
"""

import asyncio
import sys
import os

# Supaya bisa import dari folder app/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.services.whatsapp import WAHAClient


TARGET_NUMBER = "62818835535"  # <-- ganti dengan nomor WA tujuan


async def main():
    client = WAHAClient()

    print("=" * 50)
    print("  WA Send Test")
    print("=" * 50)

    # 1. Cek koneksi WAHA dulu
    print("\n[1] Cek status WAHA session...")
    connected = await client.is_connected()
    if not connected:
        print("GAGAL: WAHA session tidak WORKING.")
        print("Pastikan kamu sudah scan QR code di http://localhost:3000")
        return

    print("OK: WAHA session aktif!")

    # 2. Kirim pesan test
    print(f"\n[2] Kirim pesan ke {TARGET_NUMBER}...")
    try:
        result = await client.send_text(
            TARGET_NUMBER,
            "Halo! Ini pesan test dari WA Sales Agent 🤖"
        )
        print(f"OK: Pesan terkirim! Response: {result}")
    except Exception as e:
        print(f"GAGAL: {e}")
        return

    # 3. Test dengan efek typing
    print(f"\n[3] Kirim pesan dengan efek typing...")
    try:
        result = await client.send_text_with_typing(
            TARGET_NUMBER,
            "Ini pesan kedua, dengan efek mengetik dulu ✅",
            typing_ms=2000
        )
        print(f"OK: Pesan dengan typing terkirim!")
    except Exception as e:
        print(f"GAGAL: {e}")

    print("\nSelesai!")


if __name__ == "__main__":
    asyncio.run(main())
