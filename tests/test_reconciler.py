import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock
from src.auditor.reconciler import Reconciler
from src.models.ledger import TransactionStatus


@pytest.fixture
def reconciler():
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_indexer = MagicMock()
    return Reconciler(session=mock_session, indexer=mock_indexer)


@pytest.mark.asyncio
async def test_reconcile_settles_confirmed_tx(reconciler):
    tx_id = uuid.uuid4()
    mock_tx = MagicMock()
    mock_tx.status = TransactionStatus.BROADCAST
    mock_tx.tx_hash = "0xabc"
    reconciler.session.get.return_value = mock_tx
    reconciler.indexer.get_receipt.return_value = {"status": 1}

    await reconciler.sync(tx_id=tx_id)

    assert mock_tx.status == TransactionStatus.SETTLED
    reconciler.session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_reconcile_fails_reverted_tx(reconciler):
    tx_id = uuid.uuid4()
    mock_tx = MagicMock()
    mock_tx.status = TransactionStatus.BROADCAST
    mock_tx.tx_hash = "0xfail"
    reconciler.session.get.return_value = mock_tx
    reconciler.indexer.get_receipt.return_value = {"status": 0}

    await reconciler.sync(tx_id=tx_id)

    assert mock_tx.status == TransactionStatus.FAILED
    reconciler.session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_reconciliation_on_chain_failure_from_plan(reconciler):
    """Reproduces plan.md 4.3: on-chain failure = ledger FAILED."""
    tx_id = uuid.uuid4()
    mock_tx = MagicMock()
    mock_tx.status = TransactionStatus.BROADCAST
    mock_tx.tx_hash = "0xbad"
    reconciler.session.get.return_value = mock_tx
    reconciler.indexer.get_receipt.return_value = {"status": 0}

    await reconciler.sync(tx_id=tx_id)

    assert mock_tx.status == TransactionStatus.FAILED


@pytest.mark.asyncio
async def test_reconciliation_propagates_rpc_lookup_error(reconciler):
    tx_id = uuid.uuid4()
    mock_tx = MagicMock()
    mock_tx.status = TransactionStatus.BROADCAST
    mock_tx.tx_hash = "0xerror"
    reconciler.session.get.return_value = mock_tx
    reconciler.indexer.get_receipt.side_effect = RuntimeError("Receipt lookup failed")

    with pytest.raises(RuntimeError, match="Receipt lookup failed"):
        await reconciler.sync(tx_id=tx_id)

    reconciler.session.commit.assert_not_awaited()
