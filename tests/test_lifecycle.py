import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.auditor.reconciler import Reconciler
from src.models.ledger import PolicyDecision, Transaction, TransactionStatus
from src.orchestrator.lifecycle import (
    TransactionLifecycleProcessor,
    serialize_transaction_for_signing,
)


def _make_pending_tx() -> Transaction:
    return Transaction(
        id=uuid.uuid4(),
        ledger_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        to_address="0x" + "a" * 40,
        amount=Decimal("10"),
        status=TransactionStatus.PENDING,
        policy_decision=PolicyDecision.ALLOW,
    )


def test_serialize_transaction_for_signing_is_stable():
    tx = _make_pending_tx()

    payload = serialize_transaction_for_signing(tx)

    assert str(tx.id).encode() in payload
    assert tx.to_address.encode() in payload
    assert b"10" in payload


@pytest.mark.asyncio
async def test_process_pending_signs_and_broadcasts_transaction():
    tx = _make_pending_tx()
    session = AsyncMock()
    session.add = MagicMock()
    session.get.return_value = tx

    signer = MagicMock()
    signer.sign.return_value = b"signed-payload"

    broadcaster = MagicMock()
    broadcaster.broadcast.return_value = "0x" + "1" * 64

    processor = TransactionLifecycleProcessor(
        session=session,
        signer=signer,
        broadcaster=broadcaster,
        active_shares=[(1, b"share-1"), (2, b"share-2")],
    )

    tx_hash = await processor.process_pending(tx.id)

    assert tx_hash == "0x" + "1" * 64
    assert tx.status == TransactionStatus.BROADCAST
    assert tx.tx_hash == tx_hash
    signer.sign.assert_called_once()
    broadcaster.broadcast.assert_called_once_with(b"signed-payload")
    assert session.commit.await_count == 2
    assert session.add.call_count == 2


@pytest.mark.asyncio
async def test_process_pending_skips_non_pending_transaction():
    tx = _make_pending_tx()
    tx.status = TransactionStatus.PENDING_REVIEW
    session = AsyncMock()
    session.get.return_value = tx
    signer = MagicMock()
    broadcaster = MagicMock()

    processor = TransactionLifecycleProcessor(
        session=session,
        signer=signer,
        broadcaster=broadcaster,
        active_shares=[],
    )

    assert await processor.process_pending(tx.id) is None
    signer.sign.assert_not_called()
    broadcaster.broadcast.assert_not_called()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_mock_lifecycle_e2e_settles_broadcast_transaction():
    tx = _make_pending_tx()
    session = AsyncMock()
    session.add = MagicMock()
    session.get.return_value = tx

    signer = MagicMock()
    signer.sign.return_value = b"signed-payload"

    broadcaster = MagicMock()
    broadcaster.broadcast.return_value = "0x" + "2" * 64

    processor = TransactionLifecycleProcessor(
        session=session,
        signer=signer,
        broadcaster=broadcaster,
        active_shares=[(1, b"share-1"), (2, b"share-2")],
    )
    tx_hash = await processor.process_pending(tx.id)

    assert tx_hash == "0x" + "2" * 64
    assert tx.status == TransactionStatus.BROADCAST

    indexer = MagicMock()
    indexer.get_receipt.return_value = {"status": 1}
    reconciler = Reconciler(session=session, indexer=indexer)

    await reconciler.sync(tx.id)

    assert tx.status == TransactionStatus.SETTLED
    assert session.commit.await_count == 3
    assert session.add.call_count == 3
