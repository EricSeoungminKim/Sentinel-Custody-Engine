import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Numeric, String, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from src.database import Base


class TransactionStatus(str, enum.Enum):
    PENDING = "PENDING"
    SIGNED = "SIGNED"
    BROADCAST = "BROADCAST"
    SETTLED = "SETTLED"
    FAILED = "FAILED"
    PENDING_REVIEW = "PENDING_REVIEW"


class PolicyDecision(str, enum.Enum):
    ALLOW = "ALLOW"
    CHALLENGE = "CHALLENGE"
    BLOCK = "BLOCK"


class Ledger(Base):
    __tablename__ = "ledgers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    balance: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False, default=Decimal("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="ledger")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ledger_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ledgers.id"), nullable=False)
    to_address: Mapped[str] = mapped_column(String(42), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    status: Mapped[TransactionStatus] = mapped_column(SAEnum(TransactionStatus), default=TransactionStatus.PENDING)
    policy_decision: Mapped[PolicyDecision] = mapped_column(SAEnum(PolicyDecision), nullable=True)
    tx_hash: Mapped[str | None] = mapped_column(String(66), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    ledger: Mapped["Ledger"] = relationship(back_populates="transactions")
