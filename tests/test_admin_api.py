import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("SENTINEL_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/x")
os.environ.setdefault("WEB3_RPC_URL", "https://x")

from src.database import get_session
from src.main import create_app
from src.models.ledger import Ledger, PolicyDecision, Transaction, TransactionStatus
from src.models.whitelist import WhitelistEntry


class _ScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _ExecuteResult:
    def __init__(self, rows=None, scalar_rows=None, rowcount=1):
        self._rows = rows or []
        self._scalar_rows = scalar_rows or []
        self.rowcount = rowcount

    def scalars(self):
        return _ScalarResult(self._scalar_rows)

    def all(self):
        return self._rows


@pytest_asyncio.fixture
async def client_and_session():
    app = create_app()
    session = AsyncMock()
    session.add = MagicMock()

    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-API-Key": "test-key"},
    ) as client:
        yield client, session
    app.dependency_overrides.clear()


def _tx() -> Transaction:
    return Transaction(
        id=uuid.uuid4(),
        ledger_id=uuid.uuid4(),
        to_address="0x" + "a" * 40,
        amount=Decimal("10"),
        status=TransactionStatus.PENDING,
        policy_decision=PolicyDecision.ALLOW,
    )


async def test_list_withdrawals(client_and_session):
    client, session = client_and_session
    session.execute.return_value = _ExecuteResult(scalar_rows=[_tx()])

    resp = await client.get("/withdrawals")

    assert resp.status_code == 200
    assert resp.json()[0]["status"] == "PENDING"


async def test_list_ledgers(client_and_session):
    client, session = client_and_session
    ledger = Ledger(id=uuid.uuid4(), name="demo", balance=Decimal("100"))
    ledger.created_at = datetime.now(timezone.utc)
    session.execute.return_value = _ExecuteResult(scalar_rows=[ledger])

    resp = await client.get("/ledgers")

    assert resp.status_code == 200
    assert resp.json()[0]["name"] == "demo"


async def test_list_ledger_transactions(client_and_session):
    client, session = client_and_session
    ledger = Ledger(id=uuid.uuid4(), name="demo", balance=Decimal("100"))
    session.get.return_value = ledger
    session.execute.return_value = _ExecuteResult(scalar_rows=[_tx()])

    resp = await client.get(f"/ledgers/{ledger.id}/transactions")

    assert resp.status_code == 200
    assert resp.json()[0]["status"] == "PENDING"


async def test_add_and_delete_whitelist(client_and_session):
    client, session = client_and_session

    async def refresh(obj):
        obj.id = uuid.uuid4()
        obj.created_at = datetime.now(timezone.utc)

    session.refresh.side_effect = refresh

    resp = await client.post("/whitelist", json={"address": "0x" + "b" * 40, "label": "vendor"})

    assert resp.status_code == 200
    assert resp.json()["label"] == "vendor"

    session.execute.return_value = _ExecuteResult(rowcount=1)
    resp = await client.delete("/whitelist/" + "0x" + "b" * 40)
    assert resp.status_code == 204


async def test_stats(client_and_session):
    client, session = client_and_session
    session.scalar.side_effect = [2, 1, 3]
    session.execute.side_effect = [
        _ExecuteResult(rows=[(TransactionStatus.PENDING, 1), (TransactionStatus.SETTLED, 1)]),
        _ExecuteResult(rows=[(PolicyDecision.ALLOW, 2)]),
    ]

    resp = await client.get("/stats")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_transactions"] == 2
    assert body["by_status"]["PENDING"] == 1
    assert body["by_policy_decision"]["ALLOW"] == 2


async def test_reconcile_transaction(client_and_session):
    client, session = client_and_session
    tx = _tx()
    tx.status = TransactionStatus.BROADCAST
    tx.tx_hash = "0x" + "1" * 64
    session.get.return_value = tx

    async def sync(tx_id):
        tx.status = TransactionStatus.SETTLED

    with patch("src.gatekeeper.admin_router.Reconciler") as reconciler_cls:
        reconciler_cls.return_value.sync = AsyncMock(side_effect=sync)
        resp = await client.post(f"/transactions/{tx.id}/reconcile")

    assert resp.status_code == 200
    assert resp.json()["status"] == "SETTLED"
