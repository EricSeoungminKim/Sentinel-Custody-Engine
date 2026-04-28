from decimal import Decimal
import uuid

import pytest
from dotenv import dotenv_values
from eth_account import Account
from sqlalchemy import delete, text
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from web3 import Web3

from src.auditor.indexer import OnChainIndexer
from src.auditor.reconciler import Reconciler
from src.models.audit import TransactionAuditLog
from src.models.ledger import Ledger, PolicyDecision, Transaction, TransactionStatus
from src.orchestrator.broadcast import BroadcastGateway
from src.orchestrator.ethereum_signing import EthereumSigner
from src.orchestrator.lifecycle import EthereumTransactionLifecycleProcessor
from src.orchestrator.transaction_builder import EthereumTransactionBuilder

SEPOLIA_CHAIN_ID = 11155111


def _env_value(name: str) -> str | None:
    dotenv_value = dotenv_values(".env").get(name)
    if dotenv_value:
        return str(dotenv_value)
    return None


def _database_url() -> str:
    database_url = _env_value("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL is not configured in .env")
    return database_url


def _sepolia_private_key() -> bytes:
    private_key = _env_value("SEPOLIA_TEST_PRIVATE_KEY")
    if not private_key:
        pytest.skip("SEPOLIA_TEST_PRIVATE_KEY is not configured in .env")

    private_key = private_key.removeprefix("0x")
    if len(private_key) != 64:
        pytest.skip("SEPOLIA_TEST_PRIVATE_KEY must be a 32-byte hex private key")
    return bytes.fromhex(private_key)


def _sepolia_w3() -> Web3:
    rpc_url = _env_value("WEB3_RPC_URL")
    if not rpc_url:
        pytest.skip("WEB3_RPC_URL is not configured in .env")

    w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 15}))
    chain_id = w3.eth.chain_id
    if chain_id != SEPOLIA_CHAIN_ID:
        pytest.skip(f"expected Sepolia chain id {SEPOLIA_CHAIN_ID}, got {chain_id}")
    return w3


@pytest.fixture
async def db_session():
    engine = create_async_engine(_database_url(), echo=False)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("select 1"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"database unavailable: {exc}")

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.sepolia_broadcast
@pytest.mark.asyncio
async def test_db_backed_real_sepolia_lifecycle_records_tx_hash_and_settles(db_session):
    w3 = _sepolia_w3()
    private_key = _sepolia_private_key()
    from_address = Account.from_key(private_key).address
    balance = w3.eth.get_balance(from_address)
    if balance <= 0:
        pytest.skip(f"test wallet has no Sepolia ETH: {from_address}")

    ledger_id = uuid.uuid4()
    tx_id = uuid.uuid4()
    ledger = Ledger(
        id=ledger_id,
        name="db-sepolia-e2e-ledger",
        balance=Decimal("100000"),
    )
    tx = Transaction(
        id=tx_id,
        ledger_id=ledger_id,
        to_address=from_address,
        amount=Decimal("0.000000000000000001"),
        status=TransactionStatus.PENDING,
        policy_decision=PolicyDecision.ALLOW,
    )
    db_session.add_all([ledger, tx])
    await db_session.commit()

    try:
        processor = EthereumTransactionLifecycleProcessor(
            session=db_session,
            transaction_builder=EthereumTransactionBuilder(
                w3=w3,
                from_address=from_address,
                chain_id=SEPOLIA_CHAIN_ID,
            ),
            signer=EthereumSigner(private_key),
            broadcaster=BroadcastGateway(w3),
        )

        tx_hash = await processor.process_pending(tx_id)
        print(f"DB-backed Sepolia tx hash: {tx_hash}")
        print(f"DB-backed Sepolia tx url: https://sepolia.etherscan.io/tx/{tx_hash}")

        broadcast_tx = await db_session.get(Transaction, tx_id)
        assert broadcast_tx is not None
        assert broadcast_tx.status == TransactionStatus.BROADCAST
        assert broadcast_tx.tx_hash == tx_hash

        w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
        reconciler = Reconciler(session=db_session, indexer=OnChainIndexer(w3))
        await reconciler.sync(tx_id)

        settled_tx = await db_session.get(Transaction, tx_id)
        assert settled_tx is not None
        assert settled_tx.status == TransactionStatus.SETTLED
        assert settled_tx.settled_at is not None
        audit_rows = (
            await db_session.execute(
                select(TransactionAuditLog)
                .where(TransactionAuditLog.transaction_id == tx_id)
                .order_by(TransactionAuditLog.created_at)
            )
        ).scalars().all()
        assert [row.event_type for row in audit_rows] == ["SIGNED", "BROADCAST", "SETTLED"]
    finally:
        await db_session.execute(delete(TransactionAuditLog).where(TransactionAuditLog.transaction_id == tx_id))
        await db_session.execute(delete(Transaction).where(Transaction.id == tx_id))
        await db_session.execute(delete(Ledger).where(Ledger.id == ledger_id))
        await db_session.commit()
