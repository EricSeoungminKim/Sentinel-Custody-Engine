import re
import uuid
from decimal import Decimal
from pydantic import BaseModel, field_validator

_ETH_ADDR_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")


class WithdrawalRequest(BaseModel):
    ledger_id: uuid.UUID
    to_address: str
    amount: Decimal

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("amount must be positive")
        return v

    @field_validator("to_address")
    @classmethod
    def address_must_be_valid_eth(cls, v: str) -> str:
        if not _ETH_ADDR_RE.match(v):
            raise ValueError("to_address must be a valid Ethereum address (0x + 40 hex chars)")
        return v


class WithdrawalResponse(BaseModel):
    transaction_id: uuid.UUID
    decision: str
    message: str


class TransactionStatusResponse(BaseModel):
    transaction_id: uuid.UUID
    ledger_id: uuid.UUID
    to_address: str
    amount: Decimal
    status: str
    policy_decision: str | None
    tx_hash: str | None


class AuditLogResponse(BaseModel):
    transaction_id: uuid.UUID
    event_type: str
    status: str | None
    tx_hash: str | None
    message: str | None
    created_at: str


class ProcessTransactionResponse(BaseModel):
    transaction_id: uuid.UUID | None
    tx_hash: str | None
    message: str


class LedgerResponse(BaseModel):
    id: uuid.UUID
    name: str
    balance: Decimal
    created_at: str


class WhitelistEntryRequest(BaseModel):
    address: str
    label: str | None = None

    @field_validator("address")
    @classmethod
    def address_must_be_valid_eth(cls, v: str) -> str:
        if not _ETH_ADDR_RE.match(v):
            raise ValueError("address must be a valid Ethereum address (0x + 40 hex chars)")
        return v


class WhitelistEntryResponse(BaseModel):
    id: uuid.UUID
    address: str
    label: str | None
    created_at: str


class ReconcileTransactionResponse(BaseModel):
    transaction_id: uuid.UUID
    status: str
    message: str


class StatsResponse(BaseModel):
    total_transactions: int
    by_status: dict[str, int]
    by_policy_decision: dict[str, int]
    total_ledgers: int
    total_whitelist_entries: int
