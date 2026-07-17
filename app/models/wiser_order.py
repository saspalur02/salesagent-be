from datetime import datetime
from sqlalchemy import String, Integer, BigInteger, DateTime, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base


class AisoCounter(Base):
    """
    Counter nomor SO per-periode (YYMM) untuk order yang dibuat AI Agent.
    Format nomor akhir: AISO/YYMM/NNNNN (NNNNN reset tiap bulan).
    Increment dilakukan atomik (row-lock) di generator.
    """
    __tablename__ = "aiso_counter"

    periode: Mapped[str] = mapped_column(String(4), primary_key=True)  # 'YYMM'
    last_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WiserOrder(Base):
    """
    Audit & idempotensi pengiriman final order ke Wiser (tos.orderpembelian).
    Satu baris = satu upaya kirim. `externalid` (id baris) dipakai sebagai
    tasksalesid di payload Wiser; `noso` sebagai tasksalesnoso.
    """
    __tablename__ = "wiser_order"
    __table_args__ = (
        UniqueConstraint("noso", "sotype", name="uq_wiser_order_noso_sotype"),
    )

    externalid: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    noso: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    sotype: Mapped[str] = mapped_column(String(20), nullable=False)
    toko_id: Mapped[str] = mapped_column(String(50), index=True)
    tokoidwarisan: Mapped[str | None] = mapped_column(String(50), nullable=True)
    draft_order_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending | success | failed
    wisertosopid: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    errormessage: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)      # JSON request
    response: Mapped[str | None] = mapped_column(Text, nullable=True)     # JSON response
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
