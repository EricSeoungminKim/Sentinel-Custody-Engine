import uuid

from eth_account import Account
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from web3 import Web3

from src.config import get_settings
from src.models.ledger import Transaction, TransactionStatus
from src.orchestrator.broadcast import BroadcastGateway
from src.orchestrator.ethereum_signing import EthereumSigner
from src.orchestrator.lifecycle import EthereumTransactionLifecycleProcessor
from src.orchestrator.transaction_builder import EthereumTransactionBuilder

SEPOLIA_CHAIN_ID = 11155111


def _test_private_key() -> bytes:
    key = get_settings().sepolia_test_private_key
    if not key:
        raise RuntimeError("SEPOLIA_TEST_PRIVATE_KEY is required for local worker processing")
    return bytes.fromhex(key.removeprefix("0x"))


def _processor(session: AsyncSession) -> EthereumTransactionLifecycleProcessor:
    private_key = _test_private_key()
    from_address = Account.from_key(private_key).address
    w3 = Web3(Web3.HTTPProvider(get_settings().web3_rpc_url, request_kwargs={"timeout": 15}))
    return EthereumTransactionLifecycleProcessor(
        session=session,
        transaction_builder=EthereumTransactionBuilder(
            w3=w3,
            from_address=from_address,
            chain_id=SEPOLIA_CHAIN_ID,
        ),
        signer=EthereumSigner(private_key),
        broadcaster=BroadcastGateway(w3),
    )


async def process_pending_transaction(session: AsyncSession, tx_id: uuid.UUID) -> str | None:
    return await _processor(session).process_pending(tx_id)


async def process_next_pending_transaction(session: AsyncSession) -> tuple[uuid.UUID, str] | None:
    result = await session.execute(
        select(Transaction)
        .where(Transaction.status == TransactionStatus.PENDING)
        .order_by(Transaction.created_at)
        .limit(1)
    )
    tx = result.scalar_one_or_none()
    if tx is None:
        return None
    tx_hash = await process_pending_transaction(session, tx.id)
    if tx_hash is None:
        return None
    return tx.id, tx_hash
