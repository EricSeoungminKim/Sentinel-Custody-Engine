import os
import pytest
import pytest_asyncio
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch

os.environ.setdefault("SENTINEL_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/x")
os.environ.setdefault("WEB3_RPC_URL", "https://x")

from src.main import create_app


@pytest_asyncio.fixture
async def client():
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-API-Key": "test-key"},
    ) as ac:
        yield ac


async def test_withdrawal_blocked_non_whitelist(client):
    payload = {"ledger_id": "00000000-0000-0000-0000-000000000001",
               "to_address": "0x" + "b" * 40, "amount": "10.0"}
    with patch("src.gatekeeper.router.fetch_whitelist", new_callable=AsyncMock, return_value=set()):
        with patch("src.gatekeeper.router.fetch_daily_spent", new_callable=AsyncMock, return_value=Decimal("0")):
            with patch("src.gatekeeper.router.save_transaction", new_callable=AsyncMock):
                resp = await client.post("/withdrawals", json=payload)
    assert resp.status_code == 200
    assert resp.json()["decision"] == "BLOCK"


async def test_withdrawal_allowed(client):
    payload = {"ledger_id": "00000000-0000-0000-0000-000000000001",
               "to_address": "0x" + "a" * 40, "amount": "10.0"}
    with patch("src.gatekeeper.router.fetch_whitelist", new_callable=AsyncMock, return_value={"0x" + "a" * 40}):
        with patch("src.gatekeeper.router.fetch_daily_spent", new_callable=AsyncMock, return_value=Decimal("0")):
            with patch("src.gatekeeper.router.save_transaction", new_callable=AsyncMock):
                resp = await client.post("/withdrawals", json=payload)
    assert resp.status_code == 200
    assert resp.json()["decision"] == "ALLOW"


async def test_unauthorized_request():
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        resp = await ac.post("/withdrawals", json={})
    assert resp.status_code == 401


async def test_get_withdrawal_status(client):
    tx_id = "00000000-0000-0000-0000-000000000111"
    mock_tx = type("Tx", (), {
        "id": tx_id,
        "ledger_id": "00000000-0000-0000-0000-000000000001",
        "to_address": "0x" + "a" * 40,
        "amount": Decimal("10"),
        "status": type("Status", (), {"value": "PENDING"})(),
        "policy_decision": type("Decision", (), {"value": "ALLOW"})(),
        "tx_hash": None,
    })()
    with patch("src.gatekeeper.router.AsyncSession.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_tx
        resp = await client.get(f"/withdrawals/{tx_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "PENDING"


async def test_process_next_no_pending(client):
    with patch("src.gatekeeper.router.process_next_pending_transaction", new_callable=AsyncMock, return_value=None):
        resp = await client.post("/withdrawals/process-next")
    assert resp.status_code == 200
    assert resp.json()["message"] == "No pending transaction"
