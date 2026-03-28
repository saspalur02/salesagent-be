from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Text, Integer, JSON, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base


class WACustomerMap(Base):
    """
    Mapping nomor WhatsApp → toko_id di ERP.
    Disimpan setelah toko berhasil diidentifikasi
    supaya tidak perlu tanya ulang di percakapan berikutnya.
    """
    __tablename__ = "wa_customer_map"

    wa_number: Mapped[str] = mapped_column(String(20), primary_key=True)
    toko_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    toko_name: Mapped[str] = mapped_column(String(200), nullable=False)
    toko_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DraftOrder(Base):
    """
    Menyimpan draft order sementara sambil menunggu
    finalisasi dari admin penjualan.
    """
    __tablename__ = "draft_order"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wa_number: Mapped[str] = mapped_column(String(20), index=True)
    toko_id: Mapped[str] = mapped_column(String(50), index=True)
    toko_name: Mapped[str] = mapped_column(String(200))
    toko_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    items: Mapped[dict] = mapped_column(JSON)         # list item order
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending | finalized | cancelled
    admin_wa: Mapped[str | None] = mapped_column(String(20), nullable=True)
    so_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ConversationLog(Base):
    """Log percakapan untuk audit trail."""
    __tablename__ = "conversation_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wa_number: Mapped[str] = mapped_column(String(20), index=True)
    toko_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    role: Mapped[str] = mapped_column(String(10))     # user | assistant
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
