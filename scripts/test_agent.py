"""
Test AI Agent — flow toko dan admin.
Jalankan: python scripts/test_agent.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from app.services.ai import SalesAgent
from app.services.erp import ERPClient


class MockERPClient(ERPClient):
    async def find_toko(self, nama_toko: str, alamat: str = ""):
        if "sumber" in nama_toko.lower():
            return [{"toko_id": "TOKO-001", "name": "Toko Sumber Rejeki", "address": "Jl. Mawar No.5, Bandung"}]
        return []

    async def get_products(self, active_only=True):
        return [
            {"code": "MGREF5L", "name": "Minyak Goreng Refina 5L", "alias": "minyak goreng refina", "category": "FMCG", "uom": "Karton", "price": 148000},
            {"code": "TPGSG25K", "name": "Tepung Terigu Segitiga 25Kg", "alias": "tepung segitiga", "category": "FMCG", "uom": "Sak", "price": 185000},
        ]

    async def get_price(self, product_code, customer_id):
        prices = {"MGREF5L": 145000, "TPGSG25K": 180000}
        return {"price": prices.get(product_code, 100000)}

    async def get_stock(self, product_code):
        return {"product_code": product_code, "qty_available": 50, "uom": "Karton", "warehouse": "Gudang Utama"}

    async def create_sales_order(self, payload):
        total = sum(i.get("qty", 0) * i.get("price", 0) for i in payload.get("lines", []))
        return {"so_number": "SO-2026-00123", "status": "draft", "total": total, "estimated_delivery": "2 hari kerja"}


async def test_toko():
    print("\n" + "="*55)
    print("  TEST MODE TOKO")
    print("="*55)

    erp = MockERPClient()
    agent = SalesAgent(erp)
    history = []
    wa_number = "6281234567890"

    conversation = [
        "halo, saya dari Toko Sumber Rejeki di Jl Mawar Bandung",
        "mau order minyak goreng 10 karton sama tepung 5 sak",
        "ya betul, konfirmasi",
    ]

    for msg in conversation:
        print(f"\nToko : {msg}")
        response = await agent.process_toko(msg, wa_number, history)
        print(f"Agent: {response}")
        history.append({"role": "user", "content": msg})
        history.append({"role": "assistant", "content": response})
        print("-"*55)


async def test_admin():
    print("\n" + "="*55)
    print("  TEST MODE ADMIN")
    print("="*55)

    erp = MockERPClient()
    agent = SalesAgent(erp)
    history = []

    final_order = (
        "Final order Toko Sumber Rejeki:\n"
        "- Minyak Goreng Refina 5L x 10 karton @ 145000\n"
        "- Tepung Terigu 25kg x 5 sak @ 180000\n"
        "toko_id: TOKO-001"
    )

    print(f"\nAdmin: {final_order}")
    response = await agent.process_admin(final_order, history)
    print(f"Agent: {response}")
    print("-"*55)


async def main():
    print("="*55)
    print("  AI Agent Test — New Flow")
    print("="*55)

    from app.core.settings import get_settings
    s = get_settings()
    print(f"Model : {s.litellm_model}")
    print(f"Base  : {s.litellm_api_base or '(default)'}")

    await test_toko()
    await test_admin()
    print("\nTest selesai!")


if __name__ == "__main__":
    asyncio.run(main())
