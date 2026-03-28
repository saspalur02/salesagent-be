from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.settings import get_settings
from app.core.logging import setup_logging, get_logger
from app.db.database import engine, Base
from app.db.redis_client import get_redis
from app.api.routes import webhook, health

settings = get_settings()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────
    setup_logging()
    logger.info("starting wa-sales-agent", env=settings.app_env)

    # Buat tabel DB kalau belum ada
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Test koneksi Redis
    redis = await get_redis()
    await redis.ping()
    logger.info("redis connected")

    yield

    # ── Shutdown ─────────────────────────────────────
    await engine.dispose()
    logger.info("shutdown complete")


app = FastAPI(
    title="WA Sales Agent",
    description="AI Agent WhatsApp → ERP Sales Order",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if not settings.is_production else [],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["health"])
app.include_router(webhook.router, prefix="/webhook", tags=["webhook"])
