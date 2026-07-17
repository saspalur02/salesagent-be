import json
import re
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import get_settings
from app.core.logging import get_logger
from app.core.phone import normalize_phone, cache_waha_id, get_real_phone
from app.db.database import get_db
from app.db.redis_client import get_redis, SessionStore
from app.models.webhook import WAHAPayload, EvolutionPayload
from app.services.whatsapp import get_wa_client
from app.services.whatsapp.base import WhatsAppClient
from app.services.erp import ERPClient
from app.services.ai import SalesAgent


settings = get_settings()
logger = get_logger(__name__)
router = APIRouter()

MAX_HISTORY = 20

MSG_WELCOME = (
    "Halo! Selamat datang 👋\n\n"
    "Saya asisten pemesanan spare part kendaraan.\n"
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
    print("=== RAW PAYLOAD (WAHA) ===")
    print(raw.decode())
    print("==========================")

    try:
        payload_dict = await request.json()
        waha = WAHAPayload(**payload_dict)
    except Exception as e:
        logger.warning("webhook_parse_error", error=str(e))
        raise HTTPException(status_code=400, detail="Invalid payload")

    # Cache @lid ID dari pesan masuk
    raw_from = payload_dict.get("payload", {}).get("from", "")
    cache_waha_id(raw_from)

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
        wa_number = payload_dict.get("payload", {}).get("from")
        if wa_number and "@" in wa_number:
            wa_number = wa_number.split("@")[0]
        print(f"DEBUG: Hotfix WA_NUMBER manual -> {wa_number}")

    if not wa_number:
        return {"status": "ignored", "reason": "no_number"}

    # Resolve ke nomor HP asli dari @lid (khusus WAHA)
    if raw_from:
        wa_number = await get_real_phone(raw_from)
        print(f"DEBUG: Real phone resolved -> {wa_number}")

    await _dispatch(wa_number, waha.get_message_type(), waha.get_message_body())
    return {"status": "ok"}


# Dua path: Evolution v2.3.7 memaksa webhookByEvents=true, jadi ia POST ke
# /webhook/evolution/messages-upsert (nama event ditempel). Kita terima juga
# path polos /webhook/evolution kalau webhookByEvents berhasil dimatikan.
@router.post("/evolution")
@router.post("/evolution/{event_path}")
async def evolution_webhook(
    request: Request,
    event_path: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    raw = await request.body()
    print(f"=== RAW PAYLOAD (EVOLUTION) [{event_path or 'root'}] ===")
    print(raw.decode())
    print("===============================")

    try:
        payload_dict = await request.json()
        evo = EvolutionPayload(**payload_dict)
    except Exception as e:
        logger.warning("webhook_parse_error", error=str(e))
        raise HTTPException(status_code=400, detail="Invalid payload")

    print(f"EVENT: {evo.event}")
    print(f"FROM_ME: {evo.is_from_me()}")
    print(f"IS_GROUP: {evo.is_group_message()}")
    print(f"WA_NUMBER: {evo.get_wa_number()}")
    print(f"TYPE: {evo.get_message_type()}")
    print(f"BODY: {evo.get_message_body()}")

    if evo.event != "messages.upsert":
        print(f"FILTERED: event={evo.event}")
        return {"status": "ignored", "reason": f"event={evo.event}"}
    if evo.is_from_me():
        print("FILTERED: from_me")
        return {"status": "ignored", "reason": "from_me"}
    if evo.is_group_message():
        print("FILTERED: group")
        return {"status": "ignored", "reason": "group_message"}

    wa_number = evo.get_wa_number()
    if not wa_number:
        return {"status": "ignored", "reason": "no_number"}

    await _dispatch(wa_number, evo.get_message_type(), evo.get_message_body())
    return {"status": "ok"}


async def _dispatch(
    wa_number: str,
    message_type: str,
    message_body: str | None,
) -> None:
    """Alur inti setelah nomor & isi pesan berhasil diekstrak.

    Provider-agnostic: client keluar dipilih via settings.wa_provider.
    """
    wa_client = get_wa_client()

    if message_type != "chat" or not message_body:
        await wa_client.send_text(wa_number, MSG_NOT_TEXT)
        return

    logger.info("message_received", wa_number=wa_number)

    # ── Init services ────────────────────────────────────────────
    erp_client = ERPClient()
    redis = await get_redis()
    session_store = SessionStore(redis)
    agent = SalesAgent(erp_client)

    # ── Deteksi: admin atau toko? ────────────────────────────────
    is_admin = wa_number in settings.admin_wa_list

    if is_admin:
        await _handle_admin(
            wa_number, message_body,
            agent, wa_client, session_store
        )
    else:
        await _handle_toko(
            wa_number, message_body,
            agent, wa_client, session_store, erp_client
        )


async def _handle_admin(
    wa_number: str,
    message: str,
    agent: SalesAgent,
    wa_client: WhatsAppClient,
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
        await wa_client.send_text(wa_number, MSG_ERROR)
        return

    await wa_client.send_text_with_typing(wa_number, response)

    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": response})
    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]
    await session_store.update(f"admin:{wa_number}", {"history": history})


async def _handle_toko(
    wa_number: str,
    message: str,
    agent: SalesAgent,
    wa_client: WhatsAppClient,
    session_store: SessionStore,
    erp_client: ERPClient,
) -> None:
    """Handle pesan dari toko."""
    session = await session_store.get(wa_number) or {}
    history = session.get("history", [])
    toko = session.get("toko")
    state = session.get("state")

    # ── Tahap konfirmasi: nomor terdaftar di >1 toko ─────────────
    if state == "awaiting_toko_choice":
        candidates = session.get("toko_candidates", [])
        chosen = _resolve_toko_choice(message, candidates)
        if chosen:
            await session_store.update(wa_number, {
                "toko": chosen,
                "state": "identified",
                "toko_candidates": [],
            })
            await wa_client.send_text_with_typing(
                wa_number,
                f"Baik, *{chosen['name']}* ✅\n\n"
                "Silakan sebutkan part yang ingin dipesan "
                "(kode part atau nama part + kendaraan).",
            )
        else:
            await wa_client.send_text_with_typing(
                wa_number,
                "Maaf, saya belum menangkap pilihannya. " + _ask_toko_choice(candidates),
            )
        return

    # ── Kontak pertama — coba identifikasi toko dari nomor WA ────
    if not history and not toko:
        try:
            candidates = await erp_client.get_toko_by_phone(wa_number)
        except Exception as e:
            logger.error("toko_by_phone_error", wa_number=wa_number, error=str(e))
            candidates = []

        if len(candidates) == 1:
            toko = candidates[0]
            await session_store.set(wa_number, {
                "history": [], "state": "identified", "toko": toko,
            })
            await wa_client.send_text_with_typing(wa_number, _greet_identified(toko))
            history = []
        elif len(candidates) > 1:
            await session_store.set(wa_number, {
                "history": [], "state": "awaiting_toko_choice",
                "toko_candidates": candidates,
            })
            await wa_client.send_text_with_typing(wa_number, _ask_toko_choice(candidates))
            return
        else:
            await wa_client.send_text_with_typing(wa_number, MSG_WELCOME)
            await session_store.set(wa_number, {"history": [], "state": "new"})
            history = []

    logger.info("toko_message", wa_number=wa_number, toko_id=(toko or {}).get("toko_id"))

    try:
        response = await agent.process_toko(
            message=message,
            wa_number=wa_number,
            history=history,
            toko=toko,
        )
    except Exception as e:
        logger.error("toko_agent_error", error=str(e))
        await wa_client.send_text(wa_number, MSG_ERROR)
        return

    await wa_client.send_text_with_typing(wa_number, response)

    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": response})
    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]
    await session_store.update(wa_number, {"history": history})
    await session_store.extend_ttl(wa_number)


def _greet_identified(toko: dict) -> str:
    """Sapaan saat toko langsung dikenali dari nomor WA."""
    addr = f"\n📍 {toko['address']}" if toko.get("address") else ""
    return (
        f"Halo *{toko['name']}* 👋{addr}\n\n"
        "Saya asisten pemesanan spare part kendaraan.\n"
        "Silakan sebutkan part yang ingin dipesan "
        "(kode part atau nama part + kendaraan)."
    )


def _ask_toko_choice(candidates: list[dict]) -> str:
    """Daftar pilihan saat nomor terdaftar di >1 toko."""
    lines = [
        f"Nomor Anda terdaftar di *{len(candidates)} toko*. "
        "Toko mana yang dimaksud?\n"
    ]
    for i, t in enumerate(candidates[:10], 1):
        addr = f" — {t['address']}" if t.get("address") else ""
        lines.append(f"{i}. *{t['name']}*{addr}")
    lines.append("\nBalas dengan *nomor* pilihan (mis. 1).")
    return "\n".join(lines)


def _resolve_toko_choice(message: str, candidates: list[dict]) -> dict | None:
    """Cocokkan balasan user ke salah satu kandidat toko.

    Urutan: nomor urut → kode toko → nama toko.
    """
    if not candidates:
        return None
    text = message.strip().lower()

    # 1. Nomor urut di awal pesan (mis. "1", "2. ...")
    m = re.match(r"^\s*(\d+)", text)
    if m:
        idx = int(m.group(1))
        if 1 <= idx <= len(candidates):
            return candidates[idx - 1]

    # 2. Kode toko muncul di teks
    for c in candidates:
        kode = (c.get("kode") or "").lower()
        if kode and kode in text:
            return c

    # 3. Nama toko muncul di teks
    for c in candidates:
        if c["name"].lower() in text:
            return c

    return None