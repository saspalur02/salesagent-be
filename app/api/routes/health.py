from fastapi import APIRouter
from app.db.redis_client import get_redis

router = APIRouter()


@router.get("/health")
async def health():
    redis = await get_redis()
    redis_ok = await redis.ping()
    return {
        "status": "ok",
        "redis": "ok" if redis_ok else "error",
    }
