import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.ledger import PolicyDecision, Transaction, TransactionStatus
from src.orchestrator.worker import process_next_pending_transaction


@pytest.mark.asyncio
async def test_process_next_pending_transaction_returns_none_when_empty():
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result

    assert await process_next_pending_transaction(session) is None


@pytest.mark.asyncio
async def test_process_next_pending_transaction_processes_oldest_pending():
    session = AsyncMock()
    tx = Transaction(
        id=uuid.uuid4(),
        ledger_id=uuid.uuid4(),
        to_address="0x" + "a" * 40,
        amount=Decimal("1"),
        status=TransactionStatus.PENDING,
        policy_decision=PolicyDecision.ALLOW,
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = tx
    session.execute.return_value = result

    with patch("src.orchestrator.worker.process_pending_transaction", new_callable=AsyncMock, return_value="0xabc"):
        processed = await process_next_pending_transaction(session)

    assert processed == (tx.id, "0xabc")
