import asyncio

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.settings import get_settings
from app.core.logging import get_logger
from app.core.phone import normalize_phone

settings = get_settings()
logger = get_logger(__name__)


class EvolutionClient:
    """
    HTTP client untuk Evolution API v2 (self-hosted WhatsApp API).
    Docs: https://doc.evolution-api.com

    Berbeda dengan WAHA: Evolution menerima `number` polos (628xxx),
    tidak perlu resolusi chatId / @lid. Instance dipilih via path URL.
    """

    def __init__(self):
        self.base_url = settings.evolution_base_url.rstrip("/")
        self.instance = settings.evolution_instance
        self.headers = {
            "Content-Type": "application/json",
            "apikey": settings.evolution_api_key,
        }

    # ── Send messages ────────────────────────────────────────────

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5),
    )
    async def send_text(self, wa_number: str, text: str) -> dict:
        number = normalize_phone(wa_number)

        async with httpx.AsyncClient(headers=self.headers, timeout=15) as client:
            try:
                resp = await client.post(
                    f"{self.base_url}/message/sendText/{self.instance}",
                    json={"number": number, "text": text},
                )

                if resp.status_code not in (200, 201):
                    logger.error(
                        f"EVOLUTION_ERROR: Status {resp.status_code} - {resp.text}"
                    )
                    return {"status": "error", "code": resp.status_code}

                if not resp.content:
                    logger.warning("EVOLUTION_WARNING: Server menjawab body kosong")
                    return {"status": "ok", "detail": "empty_response"}

                logger.info("message_sent", to=number, length=len(text))
                return resp.json()

            except httpx.HTTPError as e:
                logger.error(f"NETWORK_ERROR: {str(e)}")
                raise

    async def send_typing(self, wa_number: str, duration_ms: int = 2000) -> None:
        """
        Tampilkan indikator 'mengetik...' sebelum kirim pesan.
        Best-effort: kalau gagal, jangan sampai menghentikan alur kirim.
        """
        number = normalize_phone(wa_number)
        async with httpx.AsyncClient(headers=self.headers, timeout=10) as client:
            try:
                await client.post(
                    f"{self.base_url}/chat/sendPresence/{self.instance}",
                    json={
                        "number": number,
                        "presence": "composing",
                        "delay": duration_ms,
                    },
                )
            except httpx.HTTPError as e:
                logger.warning("evolution_typing_failed", error=str(e))
        await asyncio.sleep(duration_ms / 1000)

    async def send_text_with_typing(
        self, wa_number: str, text: str, typing_ms: int = 1500
    ) -> dict:
        """Kirim pesan dengan animasi typing dulu (UX lebih natural)."""
        await self.send_typing(wa_number, typing_ms)
        return await self.send_text(wa_number, text)

    # ── Session / instance management ────────────────────────────

    async def get_session_status(self) -> dict:
        """Cek status koneksi instance WhatsApp."""
        async with httpx.AsyncClient(headers=self.headers, timeout=10) as client:
            resp = await client.get(
                f"{self.base_url}/instance/connectionState/{self.instance}",
            )
            resp.raise_for_status()
            return resp.json()

    async def is_connected(self) -> bool:
        """Return True kalau instance sedang aktif & terhubung (state == 'open')."""
        try:
            status = await self.get_session_status()
            return status.get("instance", {}).get("state") == "open"
        except Exception as e:
            logger.warning("evolution_connection_check_failed", error=str(e))
            return False
