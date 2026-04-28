import uuid
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from dotenv import dotenv_values
from sqlalchemy import delete, text
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.auditor.reconciler import Reconciler
from src.config import Settings
from src.models.audit import TransactionAuditLog
from src.models.ledger import Ledger, PolicyDecision, Transaction, TransactionStatus
from src.orchestrator.lifecycle import TransactionLifecycleProcessor


def _database_url() -> str:
    dotenv_database_url = dotenv_values(".env").get("DATABASE_URL")
    if dotenv_database_url:
        return str(dotenv_database_url)
    return Settings().database_url


@pytest.fixture
async def db_session():
    try:
        database_url = _database_url()
    except Exception as exc:
        pytest.skip(f"database settings unavailable: {exc}")

    engine = create_async_engine(database_url, echo=False)
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


@pytest.mark.asyncio
async def test_db_backed_lifecycle_e2e_settles_transaction(db_session):
    ledger_id = uuid.uuid4()
    tx_id = uuid.uuid4()
    tx_hash = "0x" + "3" * 64

    ledger = Ledger(
        id=ledger_id,
        name="lifecycle-e2e-ledger",
        balance=Decimal("100000"),
    )
    tx = Transaction(
        id=tx_id,
        ledger_id=ledger_id,
        to_address="0x" + "a" * 40,
        amount=Decimal("10"),
        status=TransactionStatus.PENDING,
        policy_decision=PolicyDecision.ALLOW,
    )

    db_session.add_all([ledger, tx])
    await db_session.commit()

    try:
        signer = MagicMock()
        signer.sign.return_value = b"signed-payload"
        broadcaster = MagicMock()
        broadcaster.broadcast.return_value = tx_hash

        processor = TransactionLifecycleProcessor(
            session=db_session,
            signer=signer,
            broadcaster=broadcaster,
            active_shares=[(1, b"share-1"), (2, b"share-2")],
        )

        returned_hash = await processor.process_pending(tx_id)

        assert returned_hash == tx_hash
        broadcast_tx = await db_session.get(Transaction, tx_id)
        assert broadcast_tx is not None
        assert broadcast_tx.status == TransactionStatus.BROADCAST
        assert broadcast_tx.tx_hash == tx_hash

        indexer = MagicMock()
        indexer.get_receipt.return_value = {"status": 1}
        reconciler = Reconciler(session=db_session, indexer=indexer)

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
