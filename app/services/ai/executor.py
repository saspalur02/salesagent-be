"""
Tool executor — menjalankan tool yang diminta LLM.
Handle 2 mode: toko dan admin.
"""
import json
from app.core.logging import get_logger
from app.core.settings import get_settings
from app.services.erp import ERPClient
from app.services.whatsapp import WAHAClient

logger = get_logger(__name__)
settings = get_settings()


class TokoToolExecutor:
    """Executor untuk mode toko."""

    def __init__(self, erp_client: ERPClient, wa_number: str):
        self.erp = erp_client
        self.wa_number = wa_number

    async def execute(self, tool_name: str, tool_args: dict) -> str:
        logger.info("tool_executing", tool=tool_name, mode="toko")
        try:
            if tool_name == "cari_toko":
                return await self._cari_toko(**tool_args)
            elif tool_name == "cari_produk":
                return await self._cari_produk(**tool_args)
            elif tool_name == "kirim_ke_admin":
                return await self._kirim_ke_admin(**tool_args)
            else:
                return f"Tool '{tool_name}' tidak dikenal."
        except Exception as e:
            logger.error("tool_error", tool=tool_name, error=str(e))
            return f"Error: {str(e)}"

    async def _cari_toko(self, nama_toko: str, alamat: str = "") -> str:
        results = await self.erp.find_toko(nama_toko, alamat)
        if not results:
            return (
                f"Toko '{nama_toko}' tidak ditemukan di database. "
                "Catat nama dan alamat toko untuk proses order tetap bisa dilanjutkan."
            )
        if len(results) == 1:
            t = results[0]
            return (
                f"Toko ditemukan:\n"
                f"- ID: {t['toko_id']}\n"
                f"- Nama: {t['name']}\n"
                f"- Alamat: {t['address']}"
            )
        # Multiple results
        lines = [f"Ditemukan {len(results)} toko, mohon konfirmasi:\n"]
        for i, t in enumerate(results[:5], 1):
            lines.append(f"{i}. {t['name']} — {t['address']}")
        return "\n".join(lines)

    async def _cari_produk(self, query: str) -> str:
        products = await self.erp.get_products(active_only=True)
        query_lower = query.lower()
        matches = [
            p for p in products
            if query_lower in p.get("name", "").lower()
            or query_lower in p.get("code", "").lower()
            or query_lower in p.get("alias", "").lower()
        ]
        if not matches:
            return f"Produk '{query}' tidak ditemukan."

        lines = [f"Ditemukan {len(matches)} produk:\n"]
        for p in matches[:5]:
            lines.append(
                f"- [{p['code']}] {p['name']} | "
                f"Rp {p.get('price', 0):,.0f}/{p.get('uom', 'pcs')}"
            )
        return "\n".join(lines)

    async def _kirim_ke_admin(
        self,
        toko_name: str,
        toko_address: str,
        items: list,
        toko_id: str = "UNKNOWN",
        note: str = "",
    ) -> str:
        # Format pesan untuk admin
        lines = [
            f"🛒 *DRAFT ORDER MASUK*",
            f"",
            f"*Toko:* {toko_name}",
            f"*Alamat:* {toko_address}",
            f"*Toko ID:* {toko_id}",
            f"*WA Toko:* {self.wa_number}",
            f"",
            f"*Detail Order:*",
        ]
        total = 0
        for item in items:
            subtotal = item.get("qty", 0) * item.get("price", 0)
            total += subtotal
            lines.append(
                f"- {item.get('product_name', '-')} "
                f"x {item.get('qty', 0)} {item.get('uom', '')} "
                f"@ Rp {item.get('price', 0):,.0f}"
                + (f" = Rp {subtotal:,.0f}" if subtotal > 0 else "")
            )

        if total > 0:
            lines.append(f"")
            lines.append(f"*Estimasi Total: Rp {total:,.0f}*")

        if note:
            lines.append(f"")
            lines.append(f"*Catatan:* {note}")

        lines.append(f"")
        lines.append(f"_Silakan konfirmasi langsung ke toko dan kirim final order ke saya._")

        pesan_admin = "\n".join(lines)

        # Kirim ke semua nomor admin
        waha = WAHAClient()
        admin_numbers = settings.admin_wa_list
        if not admin_numbers:
            logger.warning("no_admin_wa_configured")
            return "Draft order tersimpan tapi nomor admin belum dikonfigurasi."

        for admin_no in admin_numbers:
            try:
                await waha.send_text(admin_no, pesan_admin)
                logger.info("draft_sent_to_admin", admin=admin_no, toko=toko_name)
            except Exception as e:
                logger.error("send_admin_failed", admin=admin_no, error=str(e))

        return "Draft order berhasil dikirim ke admin penjualan."


class AdminToolExecutor:
    """Executor untuk mode admin."""

    def __init__(self, erp_client: ERPClient):
        self.erp = erp_client

    async def execute(self, tool_name: str, tool_args: dict) -> str:
        logger.info("tool_executing", tool=tool_name, mode="admin")
        try:
            if tool_name == "cari_produk":
                return await self._cari_produk(**tool_args)
            elif tool_name == "cek_stok":
                return await self._cek_stok(**tool_args)
            elif tool_name == "buat_sales_order":
                return await self._buat_sales_order(**tool_args)
            else:
                return f"Tool '{tool_name}' tidak dikenal."
        except Exception as e:
            logger.error("tool_error", tool=tool_name, error=str(e))
            return f"Error: {str(e)}"

    async def _cari_produk(self, query: str) -> str:
        products = await self.erp.get_products(active_only=True)
        query_lower = query.lower()
        matches = [
            p for p in products
            if query_lower in p.get("name", "").lower()
            or query_lower in p.get("code", "").lower()
            or query_lower in p.get("alias", "").lower()
        ]
        if not matches:
            return f"Produk '{query}' tidak ditemukan."
        lines = [f"Ditemukan {len(matches)} produk:\n"]
        for p in matches[:5]:
            lines.append(
                f"- [{p['code']}] {p['name']} | "
                f"Rp {p.get('price', 0):,.0f}/{p.get('uom', 'pcs')}"
            )
        return "\n".join(lines)

    async def _cek_stok(self, product_code: str) -> str:
        stock = await self.erp.get_stock(product_code)
        qty = stock.get("qty_available", 0)
        uom = stock.get("uom", "")
        warehouse = stock.get("warehouse", "Gudang Utama")
        if qty <= 0:
            return f"Stok {product_code} habis di {warehouse}."
        return f"Stok {product_code}: *{qty} {uom}* tersedia di {warehouse}."

    async def _buat_sales_order(
        self, toko_id: str, items: list, note: str = ""
    ) -> str:
        payload = {
            "toko_id": toko_id,
            "note": note or "Final order via WhatsApp Admin",
            "lines": items,
        }
        result = await self.erp.create_sales_order(payload)
        so_number = result.get("so_number", "-")
        total = result.get("total", 0)
        delivery = result.get("estimated_delivery", "")
        return (
            f"✅ Sales Order *{so_number}* berhasil dibuat!\n"
            f"Total: Rp {total:,.0f}\n"
            f"Estimasi pengiriman: {delivery}"
        )
