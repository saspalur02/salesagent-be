"""
Tool executor — menjalankan tool yang diminta LLM.
Handle 2 mode: toko dan admin.
"""
from app.core.logging import get_logger
from app.core.settings import get_settings
from app.services.erp import ERPClient
from app.services.whatsapp import get_wa_client

logger = get_logger(__name__)
settings = get_settings()


class TokoToolExecutor:
    """Executor untuk mode toko."""

    def __init__(self, erp_client: ERPClient, wa_number: str, toko: dict | None = None):
        self.erp = erp_client
        self.wa_number = wa_number
        # Toko yang sudah teridentifikasi dari nomor WA (kalau ada) — jadi sumber
        # kebenaran untuk toko_id/nama/alamat saat kirim ke admin.
        self.toko = toko

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
        from app.services.erp.toko import find_toko_hybrid

        query = f"{nama_toko} {alamat}".strip() if alamat else nama_toko
        results = await find_toko_hybrid(query)

        if not results:
            return (
                f"Toko '{nama_toko}' tidak ditemukan di database. "
                "Pesanan akan dicatat dengan nama dan alamat yang Anda berikan."
            )

        # Hanya 1 hasil — langsung konfirmasi
        if len(results) == 1:
            t = results[0]
            return (
                f"Toko ditemukan:\n"
                f"- ID: {t['toko_id']}\n"
                f"- Nama: {t['name']}\n"
                f"- Alamat: {t['address']}"
            )

        # Banyak hasil dengan alamat — tampilkan max 10
        if alamat and len(results) > 1:
            lines = [f"Ditemukan {len(results)} toko '{nama_toko}' di area tersebut:\n"]
            for i, t in enumerate(results[:10], 1):
                lines.append(f"{i}. {t['name']} — {t['address']}")
            lines.append("\nMohon sebutkan alamat yang lebih spesifik.")
            return "\n".join(lines)

        # Banyak hasil tanpa alamat — minta alamat dulu, jangan kirim list ke LLM
        kota_list = list({t["address"].split(",")[-1].strip()
                         for t in results[:10] if t["address"]})
        kota_sample = ", ".join(kota_list[:5])
        return (
            f"Ditemukan {len(results)} toko dengan nama '{nama_toko}'.\n"
            f"Tersebar di: {kota_sample}, dll.\n\n"
            f"Mohon sebutkan *alamat* atau *kota* toko Anda."
        )

    async def _cari_produk(self, query: str) -> str:
        matches = await self.erp.search_products(query, limit=20)

        if not matches:
            return (
                f"Part '{query}' tidak ditemukan.\n"
                "Coba gunakan kata kunci lain, misalnya kode part atau nama kendaraan."
            )

        lines = [f"Ditemukan {len(matches)} opsi part yang cocok:\n"]
        for p in matches:
            kendaraan_info = ""
            if p.get("merk_kendaraan") or p.get("type_kendaraan"):
                kendaraan_info = f" | {p.get('merk_kendaraan', '')} {p.get('type_kendaraan', '')}".strip()
            lines.append(
                f"- [{p['code']}] {p['name']}{kendaraan_info} | {p.get('uom', 'pcs')}"
            )
        lines.append("\n_Mohon sebutkan nomor pilihan atau kodenya untuk memesan._")
        return "\n".join(lines)

    async def _kirim_ke_admin(
        self,
        toko_name: str,
        toko_address: str,
        items: list,
        toko_id: str = "UNKNOWN",
        note: str = "",
    ) -> str:
        # Kalau toko sudah teridentifikasi dari nomor WA, pakai data itu sebagai
        # sumber kebenaran — abaikan tebakan LLM.
        if self.toko:
            toko_id = self.toko.get("toko_id", toko_id)
            toko_name = self.toko.get("name", toko_name)
            toko_address = self.toko.get("address", toko_address)

        from app.core.phone import normalize_phone, wa_me_link

        wa_toko = normalize_phone(self.wa_number)
        lines = [
            "🛒 *DRAFT ORDER MASUK*",
            "",
            f"*Toko:* {toko_name}",
            f"*Alamat:* {toko_address}",
            f"*Toko ID:* {toko_id}",
            f"*WA Toko:* {wa_toko}",
            f"*Chat toko:* {wa_me_link(self.wa_number)}",
            "",
            "*Detail Order:*",
        ]
        for item in items:
            lines.append(
                f"- {item.get('product_name', '-')} "
                f"x {item.get('qty', 0)} {item.get('uom', '')}"
            )

        if note:
            lines.append(f"\n*Catatan:* {note}")

        lines.append("")
        lines.append("_Silakan konfirmasi ke toko dan kirim final order ke saya._")

        pesan_admin = "\n".join(lines)

        waha = get_wa_client()
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
        # Primary: ILIKE — exact keyword match, selalu ada selama ERP reachable
        matches = await self.erp.search_products(query, limit=10)

        if not matches:
            from app.services.vector import search_produk
            matches_vec = await search_produk(query, limit=5)
            if not matches_vec:
                return f"Part '{query}' tidak ditemukan."
            lines = [f"Ditemukan {len(matches_vec)} part:\n"]
            for p in matches_vec:
                lines.append(
                    f"- [{p['code']}] {p['name']} | Satuan: {p.get('uom', 'pcs')}"
                )
            return "\n".join(lines)

        lines = [f"Ditemukan {len(matches)} part:\n"]
        for p in matches:
            lines.append(
                f"- [{p['code']}] {p['name']} | Satuan: {p.get('uom', 'pcs')}"
            )
        return "\n".join(lines)

    async def _cek_stok(self, product_code: str, toko_id: str) -> str:
        stock = await self.erp.get_stock(product_code, toko_id)
        qty = stock.get("qty_available", 0)
        uom = stock.get("uom", "")
        warehouse = stock.get("warehouse", "Cabang Toko")
        if qty <= 0:
            return f"Stok {product_code} habis di {warehouse} (toko {toko_id})."
        return f"Stok *{product_code}*: {qty} {uom} tersedia di {warehouse} (toko {toko_id})."

    async def _buat_sales_order(
        self, toko_id: str, items: list, note: str = ""
    ) -> str:
        payload = {
            "toko_id": toko_id,
            "note": note or "Final order via WhatsApp Admin",
            "lines": items,
        }
        result = await self.erp.create_sales_order(payload)
        status = result.get("status")
        so_number = result.get("so_number") or "-"

        if status == "success":
            wisertosopid = result.get("wisertosopid")
            total = sum(
                float(it.get("qty", 0)) * float(it.get("price", 0)) for it in items
            )
            return (
                f"✅ Sales Order *{so_number}* berhasil dikirim ke ERP!\n"
                f"No ERP: {wisertosopid}\n"
                f"Total (incl. PPN): Rp {total:,.0f}"
            )

        if status == "duplicate":
            return (
                f"⚠️ Order ini sepertinya sudah pernah dikirim.\n"
                f"Pesan ERP: {result.get('errormessage')}"
            )

        return (
            f"❌ Gagal membuat Sales Order di ERP.\n"
            f"Penyebab: {result.get('errormessage')}"
        )
