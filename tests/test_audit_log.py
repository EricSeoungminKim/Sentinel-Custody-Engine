import uuid

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.auditor.audit_log import record_transaction_event
from src.models.ledger import TransactionStatus


@pytest.mark.asyncio
async def test_record_transaction_event_adds_audit_log():
    session = MagicMock()
    session.flush = AsyncMock()
    tx_id = uuid.uuid4()

    event = await record_transaction_event(
        session,
        tx_id,
        "BROADCAST",
        status=TransactionStatus.BROADCAST,
        tx_hash="0x" + "1" * 64,
        message="test event",
    )

    assert event.transaction_id == tx_id
    assert event.event_type == "BROADCAST"
    assert event.status == "BROADCAST"
    assert event.tx_hash == "0x" + "1" * 64
    assert event.message == "test event"
    session.add.assert_called_once_with(event)
    session.flush.assert_awaited_once()
