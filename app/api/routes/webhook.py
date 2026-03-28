import json
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import get_settings
from app.core.logging import get_logger
from app.core.phone import normalize_phone
from app.db.database import get_db
from app.db.redis_client import get_redis, SessionStore
from app.models.webhook import WAHAPayload
from app.services.whatsapp import WAHAClient
from app.services.erp import ERPClient
from app.services.ai import SalesAgent

settings = get_settings()
logger = get_logger(__name__)
router = APIRouter()

MAX_HISTORY = 20

MSG_WELCOME = (
    "Halo! Selamat datang 👋\n\n"
    "Saya asisten pemesanan produk.\n"
    "Boleh saya tahu *nama toko* dan *alamat* Anda?"
)
MSG_NOT_TEXT = (
    "Maaf, saya hanya bisa memproses pesan teks.\n"
    "Silakan ketik pesanan Anda."
)
MSG_ERROR = "Maaf, terjadi gangguan. Silakan coba beberapa saat lagi."


@router.post("/waha")
async def waha_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    raw = await request.body()
    print("=== RAW PAYLOAD ===")
    print(raw.decode())
    print("===================")

    try:
        payload_dict = await request.json()
        waha = WAHAPayload(**payload_dict)
    except Exception as e:
        logger.warning("webhook_parse_error", error=str(e))
        raise HTTPException(status_code=400, detail="Invalid payload")

    print(f"EVENT: {waha.event}")
    print(f"FROM_ME: {waha.is_from_me()}")
    print(f"IS_GROUP: {waha.is_group_message()}")
    print(f"WA_NUMBER: {waha.get_wa_number()}")
    print(f"TYPE: {waha.get_message_type()}")
    print(f"BODY: {waha.get_message_body()}")

    if waha.event != "message":
        print(f"FILTERED: event={waha.event}")
        return {"status": "ignored", "reason": f"event={waha.event}"}
    if waha.is_from_me():
        print("FILTERED: from_me")
        return {"status": "ignored", "reason": "from_me"}
    if waha.is_group_message():
        print("FILTERED: group")
        return {"status": "ignored", "reason": "group_message"}

    wa_number = waha.get_wa_number()
    # HOTFIX: Jika get_wa_number gagal, ambil manual dari payload raw
    if not wa_number:
        # Mencoba mengambil 'from' langsung dari dictionary payload
        wa_number = payload_dict.get("payload", {}).get("from")
        print(f"DEBUG: Hotfix WA_NUMBER manual -> {wa_number}")

    if not wa_number:
        return {"status": "ignored", "reason": "no_number"}

    message_type = waha.get_message_type()
    message_body = waha.get_message_body()

    if message_type != "chat" or not message_body:
        waha_client = WAHAClient()
        await waha_client.send_text(wa_number, MSG_NOT_TEXT)
        return {"status": "ok"}

    logger.info("message_received", wa_number=wa_number)

    # ── Init services ────────────────────────────────────────────
    waha_client = WAHAClient()
    erp_client = ERPClient()
    redis = await get_redis()
    session_store = SessionStore(redis)
    agent = SalesAgent(erp_client)

    # ── Deteksi: admin atau toko? ────────────────────────────────
    is_admin = wa_number in settings.admin_wa_list

    if is_admin:
        await _handle_admin(
            wa_number, message_body,
            agent, waha_client, session_store
        )
    else:
        await _handle_toko(
            wa_number, message_body,
            agent, waha_client, session_store
        )

    return {"status": "ok"}


async def _handle_admin(
    wa_number: str,
    message: str,
    agent: SalesAgent,
    waha_client: WAHAClient,
    session_store: SessionStore,
) -> None:
    """Handle pesan dari admin penjualan."""
    session = await session_store.get(f"admin:{wa_number}") or {}
    history = session.get("history", [])

    logger.info("admin_message", wa_number=wa_number)

    try:
        response = await agent.process_admin(
            message=message,
            history=history,
        )
    except Exception as e:
        logger.error("admin_agent_error", error=str(e))
        await waha_client.send_text(wa_number, MSG_ERROR)
        return

    await waha_client.send_text_with_typing(wa_number, response)

    # Update history admin
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": response})
    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]
    await session_store.update(f"admin:{wa_number}", {"history": history})


async def _handle_toko(
    wa_number: str,
    message: str,
    agent: SalesAgent,
    waha_client: WAHAClient,
    session_store: SessionStore,
) -> None:
    """Handle pesan dari toko."""
    session = await session_store.get(wa_number) or {}
    history = session.get("history", [])

    # Pesan pertama — sambut user
    if not history:
        await waha_client.send_text_with_typing(wa_number, MSG_WELCOME)
        await session_store.set(wa_number, {"history": [], "state": "new"})
        # Lanjut proses pesan pertama juga lewat AI
        history = []

    logger.info("toko_message", wa_number=wa_number)

    try:
        response = await agent.process_toko(
            message=message,
            wa_number=wa_number,
            history=history,
        )
    except Exception as e:
        logger.error("toko_agent_error", error=str(e))
        await waha_client.send_text(wa_number, MSG_ERROR)
        return

    await waha_client.send_text_with_typing(wa_number, response)

    # Update history toko
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": response})
    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]
    await session_store.update(wa_number, {"history": history})
    await session_store.extend_ttl(wa_number)
