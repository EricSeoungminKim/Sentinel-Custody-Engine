import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from eth_account import Account

from src.models.ledger import PolicyDecision, Transaction, TransactionStatus
from src.orchestrator.ethereum_signing import EthereumSigner
from src.orchestrator.lifecycle import EthereumTransactionLifecycleProcessor
from src.orchestrator.transaction_builder import EthereumTransactionBuilder

TEST_PRIVATE_KEY = bytes.fromhex(
    "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
)


def _pending_tx() -> Transaction:
    return Transaction(
        id=uuid.uuid4(),
        ledger_id=uuid.uuid4(),
        to_address="0x" + "a" * 40,
        amount=Decimal("0.01"),
        status=TransactionStatus.PENDING,
        policy_decision=PolicyDecision.ALLOW,
    )


@pytest.mark.asyncio
async def test_ethereum_lifecycle_builds_signs_and_broadcasts_pending_transaction():
    tx = _pending_tx()
    session = AsyncMock()
    session.add = MagicMock()
    session.get.return_value = tx

    mock_w3 = MagicMock()
    mock_w3.eth.get_transaction_count.return_value = 3
    mock_w3.eth.get_block.return_value = {"baseFeePerGas": 20_000_000_000}
    from_address = Account.from_key(TEST_PRIVATE_KEY).address
    builder = EthereumTransactionBuilder(
        w3=mock_w3,
        from_address=from_address,
        chain_id=11155111,
    )
    signer = EthereumSigner(TEST_PRIVATE_KEY)
    broadcaster = MagicMock()
    broadcaster.broadcast.return_value = "0x" + "4" * 64

    processor = EthereumTransactionLifecycleProcessor(
        session=session,
        transaction_builder=builder,
        signer=signer,
        broadcaster=broadcaster,
    )

    tx_hash = await processor.process_pending(tx.id)

    assert tx_hash == "0x" + "4" * 64
    assert tx.status == TransactionStatus.BROADCAST
    assert tx.tx_hash == tx_hash
    assert session.commit.await_count == 2

    raw_tx = broadcaster.broadcast.call_args.args[0]
    assert isinstance(raw_tx, bytes)
    assert Account.recover_transaction(raw_tx) == from_address


@pytest.mark.asyncio
async def test_ethereum_lifecycle_skips_non_pending_transaction():
    tx = _pending_tx()
    tx.status = TransactionStatus.PENDING_REVIEW
    session = AsyncMock()
    session.get.return_value = tx

    processor = EthereumTransactionLifecycleProcessor(
        session=session,
        transaction_builder=MagicMock(),
        signer=MagicMock(),
        broadcaster=MagicMock(),
    )

    assert await processor.process_pending(tx.id) is None
    session.commit.assert_not_awaited()
