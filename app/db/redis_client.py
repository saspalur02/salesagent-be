import json
import redis.asyncio as aioredis
from typing import Any
from app.core.settings import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

_redis_client: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = await aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


class SessionStore:
    """
    Menyimpan konteks percakapan per nomor WhatsApp.
    Key pattern: session:{wa_number}
    """

    PREFIX = "session"
    TTL = settings.session_ttl_seconds

    def __init__(self, redis: aioredis.Redis):
        self.redis = redis

    def _key(self, wa_number: str) -> str:
        # Normalisasi nomor dulu sebelum dijadikan key
        normalized = wa_number.lstrip("+").replace("-", "").replace(" ", "")
        return f"{self.PREFIX}:{normalized}"

    async def get(self, wa_number: str) -> dict | None:
        raw = await self.redis.get(self._key(wa_number))
        if raw:
            return json.loads(raw)
        return None

    async def set(self, wa_number: str, data: dict) -> None:
        await self.redis.setex(
            self._key(wa_number),
            self.TTL,
            json.dumps(data, ensure_ascii=False),
        )

    async def update(self, wa_number: str, updates: dict) -> dict:
        existing = await self.get(wa_number) or {}
        existing.update(updates)
        await self.set(wa_number, existing)
        return existing

    async def delete(self, wa_number: str) -> None:
        await self.redis.delete(self._key(wa_number))

    async def extend_ttl(self, wa_number: str) -> None:
        await self.redis.expire(self._key(wa_number), self.TTL)
