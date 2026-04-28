import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.audit import TransactionAuditLog
from src.models.ledger import TransactionStatus


async def record_transaction_event(
    session: AsyncSession,
    transaction_id: uuid.UUID,
    event_type: str,
    status: TransactionStatus | str | None = None,
    tx_hash: str | None = None,
    message: str | None = None,
) -> TransactionAuditLog:
    status_value = status.value if isinstance(status, TransactionStatus) else status
    event = TransactionAuditLog(
        transaction_id=transaction_id,
        event_type=event_type,
        status=status_value,
        tx_hash=tx_hash,
        message=message,
    )
    session.add(event)
    await session.flush()
    return event
