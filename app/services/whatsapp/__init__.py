import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from app.core.settings import get_settings
from app.core.logging import get_logger
from app.core.phone import to_waha_id
from app.core.phone import resolve_waha_id, from_waha_id, normalize_phone, _waha_id_cache


settings = get_settings()
logger = get_logger(__name__)


class WAHAClient:
    """
    HTTP client untuk WAHA Core (self-hosted WhatsApp HTTP API).
    Docs: https://waha.devlike.pro/docs/how-to/send-messages/
    """

    def __init__(self):
        self.base_url = settings.waha_base_url.rstrip("/")
        self.session = settings.waha_session
        self.headers = {
            "Content-Type": "application/json",
            "X-Api-Key": settings.waha_api_key,
        }
        # TAMBAHKAN BARIS INI UNTUK DEBUG
        print(f"--- DEBUG WAHA CLIENT INIT ---")
        print(f"URL: {self.base_url}")
        print(f"KEY: '{self.headers['X-Api-Key']}'")
        print(f"-------------------------------")

    # ── Send messages ────────────────────────────────────────────

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5),
    )

    async def send_text(self, wa_number: str, text: str) -> dict:
        
        chat_id = await resolve_waha_id(wa_number)
    
        async with httpx.AsyncClient(headers=self.headers, timeout=15) as client:
            try:
                resp = await client.post(
                    f"{self.base_url}/api/sendText",
                    json={"session": self.session, "chatId": chat_id, "text": text},
                )

                if resp.status_code not in [200, 201]:
                    logger.error(f"WAHA_ERROR: Status {resp.status_code} - {resp.text}")
                    return {"status": "error", "code": resp.status_code}

                if not resp.content:
                    logger.warning("WAHA_WARNING: Server menjawab dengan body kosong")
                    return {"status": "ok", "detail": "empty_response"}

                # Simpan @lid ID dari response ke cache
                data = resp.json()
                remote_lid = data.get("_data", {}).get("id", {}).get("remote")
                if remote_lid and "@lid" in remote_lid:
                    normalized = normalize_phone(wa_number)
                    from app.core.phone import _waha_id_cache
                    _waha_id_cache[normalized] = remote_lid
                    logger.info("waha_id_updated_from_response", 
                            phone=normalized, chat_id=remote_lid)

                logger.info("message_sent", to=from_waha_id(chat_id), length=len(text))
                return data

            except httpx.HTTPError as e:
                logger.error(f"NETWORK_ERROR: {str(e)}")
                raise

    async def send_typing(self, wa_number: str, duration_ms: int = 2000) -> None:
        """
        Tampilkan indikator 'mengetik...' sebelum kirim pesan.
        Membuat interaksi terasa lebih natural.
        """
        chat_id = await resolve_waha_id(wa_number)
        async with httpx.AsyncClient(headers=self.headers, timeout=10) as client:
            await client.post(
                f"{self.base_url}/api/startTyping",
                json={
                    "session": self.session,
                    "chatId": chat_id,
                },
            )
            # Tunggu sesuai durasi, lalu stop typing
            import asyncio
            await asyncio.sleep(duration_ms / 1000)
            await client.post(
                f"{self.base_url}/api/stopTyping",
                json={
                    "session": self.session,
                    "chatId": chat_id,
                },
            )

    async def send_text_with_typing(
        self, wa_number: str, text: str, typing_ms: int = 1500
    ) -> dict:
        """
        Kirim pesan dengan animasi typing dulu.
        Pakai ini sebagai pengganti send_text untuk UX yang lebih natural.
        """
        await self.send_typing(wa_number, typing_ms)
        return await self.send_text(wa_number, text)

    # ── Session management ───────────────────────────────────────

    async def get_session_status(self) -> dict:
        """Cek status koneksi WhatsApp session."""
        async with httpx.AsyncClient(headers=self.headers, timeout=10) as client:
            resp = await client.get(
                f"{self.base_url}/api/sessions/{self.session}",
            )
            resp.raise_for_status()
            return resp.json()

    async def is_connected(self) -> bool:
        """Return True kalau session sedang aktif & terhubung."""
        try:
            status = await self.get_session_status()
            return status.get("status") == "WORKING"
        except Exception as e:
            logger.warning("waha_connection_check_failed", error=str(e))
            return False


# ── Provider factory ─────────────────────────────────────────────

from app.services.whatsapp.base import WhatsAppClient  # noqa: E402
from app.services.whatsapp.evolution import EvolutionClient  # noqa: E402


def get_wa_client() -> WhatsAppClient:
    """Pilih implementasi client sesuai settings.wa_provider."""
    if settings.wa_provider.lower() == "evolution":
        return EvolutionClient()
    return WAHAClient()
