from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.customer import WACustomerMap
from app.core.phone import normalize_phone
from app.core.logging import get_logger

logger = get_logger(__name__)


class IdentityService:
    """
    Resolve nomor WhatsApp → customer_id ERP.

    Urutan lookup:
      1. Cek tabel wa_customer_map (cache lokal di DB kita)
      2. Kalau tidak ada, query ERP by phone number
      3. Kalau ketemu di ERP, simpan ke wa_customer_map
      4. Kalau tidak ketemu di mana-mana, return None (unknown user)
    """

    def __init__(self, db: AsyncSession, erp_client):
        self.db = db
        self.erp = erp_client

    async def resolve(self, wa_number: str) -> WACustomerMap | None:
        """
        Resolve nomor WA ke customer. Return WACustomerMap atau None.
        """
        normalized = normalize_phone(wa_number)

        # ── Step 1: cek local map ────────────────────────────────
        result = await self.db.execute(
            select(WACustomerMap).where(WACustomerMap.wa_number == normalized)
        )
        mapping = result.scalar_one_or_none()

        if mapping:
            logger.info("customer_resolved_from_map",
                        wa_number=normalized,
                        customer_id=mapping.customer_id)
            return mapping

        # ── Step 2: query ERP by phone ───────────────────────────
        logger.info("customer_not_in_map_querying_erp", wa_number=normalized)
        erp_customer = await self.erp.find_customer_by_phone(normalized)

        if not erp_customer:
            logger.info("customer_not_found_in_erp", wa_number=normalized)
            return None

        # ── Step 3: simpan ke local map ──────────────────────────
        mapping = WACustomerMap(
            wa_number=normalized,
            customer_id=erp_customer["id"],
            customer_name=erp_customer["name"],
            contact_name=erp_customer.get("contact_name"),
            is_verified=True,
        )
        self.db.add(mapping)
        await self.db.commit()
        await self.db.refresh(mapping)

        logger.info("customer_mapped",
                    wa_number=normalized,
                    customer_id=mapping.customer_id)
        return mapping

    async def register_manual(
        self,
        wa_number: str,
        customer_id: str,
        customer_name: str,
        contact_name: str | None = None,
    ) -> WACustomerMap:
        """
        Daftarkan mapping secara manual — dipakai saat customer
        belum terdaftar di ERP tapi sudah konfirmasi identitasnya via chat.
        is_verified=False sampai admin konfirmasi.
        """
        normalized = normalize_phone(wa_number)
        mapping = WACustomerMap(
            wa_number=normalized,
            customer_id=customer_id,
            customer_name=customer_name,
            contact_name=contact_name,
            is_verified=False,
        )
        self.db.add(mapping)
        await self.db.commit()
        await self.db.refresh(mapping)
        return mapping
