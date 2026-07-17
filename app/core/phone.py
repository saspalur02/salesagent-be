import re
import httpx
from app.core.logging import get_logger

logger = get_logger(__name__)

# Cache in-memory: nomor HP → chat ID (@lid atau @c.us)
# Di-populate dari 2 sumber:
#   1. Pesan masuk dari WAHA (via cache_waha_id)
#   2. Lookup via WAHA contacts API
_waha_id_cache: dict[str, str] = {}


def normalize_phone(number: str) -> str:
    """Bersihkan nomor HP jadi format 628xxx."""
    if "@" in number:
        return number.split("@")[0]
    digits = re.sub(r"\D", "", number)
    if digits.startswith("0"):
        digits = "62" + digits[1:]
    return digits


def phone_core(number: str) -> str:
    """
    Ambil bagian signifikan nomor HP Indonesia → bentuk kanonik '8xxxxxxxx'.

    Semua format dipetakan ke nilai yang sama, contoh:
        0818835535      → 818835535
        62818835535     → 818835535
        0062818835535   → 818835535
        +62 818-835-535 → 818835535

    Cara: buang semua non-digit, lalu kupas prefix '0062' / '62' / '0' di depan.
    """
    digits = re.sub(r"\D", "", number or "")
    if not digits:
        return ""
    if digits.startswith("0062"):
        digits = digits[4:]
    elif digits.startswith("62"):
        digits = digits[2:]
    elif digits.startswith("0"):
        digits = digits[1:]
    return digits


def wa_me_link(number: str) -> str:
    """Buat link wa.me yang selalu bisa diklik → buka chat ke nomor tsb.

    Contoh: '0818835535' / '+62 818-835-535' → 'https://wa.me/62818835535'
    """
    normalized = normalize_phone(number)
    return f"https://wa.me/{normalized}"


def to_waha_id(number: str) -> str:
    """Konversi nomor ke format @lid."""
    if "@" in number:
        return number
    return f"{normalize_phone(number)}@lid"


def from_waha_id(waha_id: str) -> str:
    """Ekstrak nomor dari format @c.us atau @lid."""
    return waha_id.split("@")[0]


def cache_waha_id(raw_from: str) -> None:
    if not raw_from or "@" not in raw_from:
        return
    if "@g.us" in raw_from:
        return
    number = raw_from.split("@")[0]
    if number:
        _waha_id_cache[number] = raw_from  # selalu update
        logger.info("waha_id_cached", phone=number, chat_id=raw_from)


async def resolve_waha_id(phone: str) -> str:
    """
    Resolve nomor HP ke chat ID yang benar.

    Prioritas:
    1. Kalau sudah ada @, langsung return (sudah berupa ID)
    2. Cek cache — bisa berisi @lid (dari pesan masuk) atau @c.us
    3. Lookup via WAHA contacts API — cek apakah ada @lid
    4. Fallback ke @c.us
    """
    from app.core.settings import get_settings
    settings = get_settings()

    # Sudah berupa chat ID
    if "@" in phone:
        return phone

    normalized = normalize_phone(phone)

    # Cek cache — prioritaskan @lid kalau ada
    if normalized in _waha_id_cache:
        cached = _waha_id_cache[normalized]
        logger.info("waha_id_from_cache", phone=normalized, chat_id=cached)
        return cached

    # Lookup via WAHA contacts API
    try:
        async with httpx.AsyncClient(
            headers={
                "Content-Type": "application/json",
                "X-Api-Key": settings.waha_api_key,
            },
            timeout=10,
        ) as client:
            resp = await client.get(
                f"{settings.waha_base_url}/api/contacts",
                params={
                    "session": settings.waha_session,
                    "contactId": f"{normalized}@c.us",
                },
            )

            print(f"DEBUG CONTACTS STATUS: {resp.status_code}")
            print(f"DEBUG CONTACTS RESPONSE: {data}")
        
            if resp.status_code == 200:
                data = resp.json()
                # Cek apakah ada @lid field di response
                lid = data.get("lid")
                chat_id = f"{lid}@lid" if lid else data.get("id")
                if chat_id:
                    _waha_id_cache[normalized] = chat_id
                    logger.info("waha_id_resolved", phone=normalized, chat_id=chat_id)
                    return chat_id

    except Exception as e:
        logger.warning("waha_id_resolve_failed", phone=normalized, error=str(e))

    # Fallback ke @c.us
    fallback = f"{normalized}@c.us"
    logger.warning("waha_id_fallback", phone=normalized, fallback=fallback)
    _waha_id_cache[normalized] = fallback
    return fallback


def clear_waha_id_cache():
    """Clear cache — pakai kalau ada perubahan nomor."""
    _waha_id_cache.clear()

# Cache mapping @lid → nomor HP asli
_lid_to_phone_cache: dict[str, str] = {}

async def get_real_phone(waha_id: str) -> str:
    """
    Lookup nomor HP asli dari @lid ID via WAHA contacts API.
    Returns nomor HP murni: "62818835535"
    """
    from app.core.settings import get_settings
    settings = get_settings()

    # Kalau tidak ada @, sudah nomor HP
    if "@" not in waha_id:
        return waha_id

    # Cek cache dulu
    if waha_id in _lid_to_phone_cache:
        return _lid_to_phone_cache[waha_id]

    try:
        async with httpx.AsyncClient(
            headers={
                "Content-Type": "application/json",
                "X-Api-Key": settings.waha_api_key,
            },
            timeout=10,
        ) as client:
            resp = await client.get(
                f"{settings.waha_base_url}/api/contacts",
                params={
                    "session": settings.waha_session,
                    "contactId": waha_id,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                number = data.get("number")
                if number:
                    _lid_to_phone_cache[waha_id] = number
                    logger.info("real_phone_resolved", waha_id=waha_id, phone=number)
                    return number
    except Exception as e:
        logger.warning("real_phone_resolve_failed", waha_id=waha_id, error=str(e))

    # Fallback — strip @lid
    return waha_id.split("@")[0]