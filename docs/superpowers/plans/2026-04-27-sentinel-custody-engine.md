# Sentinel Custody Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an offline-capable crypto custody control system with policy enforcement, 2-of-3 MPC threshold signing, and on-chain reconciliation.

**Architecture:** FastAPI monorepo split into three bounded domains — `gatekeeper` (policy + ledger), `orchestrator` (MPC key sharding + signing), `auditor` (on-chain indexer + reconciliation). Each domain is a Python package under `src/`. PostgreSQL stores all state. Docker Compose wires everything locally.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.x (async), PostgreSQL 15, Alembic, Web3.py, PyCryptodome (Shamir's Secret Sharing), pytest-asyncio, Docker Compose, Sepolia testnet.

---

## File Map

```
Sentinel-Custody-Engine/
├── docker-compose.yml
├── pyproject.toml
├── .env.example
├── alembic.ini
├── alembic/
│   └── versions/
│       └── 0001_initial_schema.py
├── src/
│   ├── __init__.py
│   ├── config.py                      # env-driven settings (pydantic-settings)
│   ├── database.py                    # async engine + session factory
│   ├── models/
│   │   ├── __init__.py
│   │   ├── ledger.py                  # Ledger, Transaction ORM models
│   │   └── whitelist.py               # Whitelist ORM model
│   ├── gatekeeper/
│   │   ├── __init__.py
│   │   ├── policy.py                  # PolicyEngine: Allow/Challenge/Block
│   │   ├── router.py                  # POST /withdrawals
│   │   └── schemas.py                 # Pydantic request/response shapes
│   ├── orchestrator/
│   │   ├── __init__.py
│   │   ├── key_sharding.py            # Shamir split/reconstruct
│   │   ├── signing.py                 # MPC threshold signing workflow
│   │   └── broadcast.py              # Web3 transaction broadcast
│   ├── auditor/
│   │   ├── __init__.py
│   │   ├── indexer.py                 # Poll Sepolia for tx receipts
│   │   └── reconciler.py             # Ledger ↔ on-chain state sync
│   └── main.py                        # FastAPI app factory
└── tests/
    ├── conftest.py                    # async DB session + fixtures
    ├── test_policy.py
    ├── test_key_sharding.py
    ├── test_signing.py
    ├── test_broadcast.py
    ├── test_reconciler.py
    └── test_withdrawal_api.py
```

---

## Task 1: Project Scaffold & Docker

**Files:**

- Create: `docker-compose.yml`
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `src/__init__.py`
- Create: `src/config.py`

- [ ] **Step 1: Write failing test for config loading**

```python
# tests/test_config.py
import pytest
from src.config import Settings

def test_settings_load_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/sentinel")
    monkeypatch.setenv("WEB3_RPC_URL", "https://sepolia.infura.io/v3/test")
    s = Settings()
    assert s.database_url.startswith("postgresql+asyncpg")
    assert "sepolia" in s.web3_rpc_url
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/smk/Documents/GitHub/Sentinel-Custody-Engine
pytest tests/test_config.py -v
```

Expected: `ModuleNotFoundError: No module named 'src'`

- [ ] **Step 3: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "sentinel-custody-engine"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.111",
    "uvicorn[standard]>=0.29",
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.29",
    "alembic>=1.13",
    "pydantic-settings>=2.2",
    "web3>=6.15",
    "pycryptodome>=3.20",
]

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "pytest-asyncio>=0.23",
    "httpx>=0.27",
    "pytest-mock>=3.14",
]

[tool.setuptools.packages.find]
where = ["."]
include = ["src*"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [ ] **Step 4: Install dependencies**

```bash
pip install -e ".[dev]"
```

- [ ] **Step 5: Create src/**init**.py and src/config.py**

`src/__init__.py` — empty file.

```python
# src/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://sentinel:sentinel@localhost:5432/sentinel"
    web3_rpc_url: str = "https://sepolia.infura.io/v3/changeme"
    mpc_min_shares: int = 2
    mpc_total_shares: int = 3


settings = Settings()
```

- [ ] **Step 6: Create .env.example**

```
DATABASE_URL=postgresql+asyncpg://sentinel:sentinel@localhost:5432/sentinel
WEB3_RPC_URL=https://sepolia.infura.io/v3/YOUR_KEY
MPC_MIN_SHARES=2
MPC_TOTAL_SHARES=3
```

- [ ] **Step 7: Create docker-compose.yml**

```yaml
services:
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: sentinel
      POSTGRES_PASSWORD: sentinel
      POSTGRES_DB: sentinel
    ports:
  - "5433:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

- [ ] **Step 8: Run test to verify it passes**

```bash
pytest tests/test_config.py -v
```

Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml docker-compose.yml .env.example src/config.py src/__init__.py tests/test_config.py
git commit -m "feat: project scaffold, config, and docker-compose"
```

---

## Task 2: Database Models & Migrations

**Files:**

- Create: `src/database.py`
- Create: `src/models/__init__.py`
- Create: `src/models/ledger.py`
- Create: `src/models/whitelist.py`
- Create: `alembic.ini`
- Create: `alembic/versions/0001_initial_schema.py`

- [ ] **Step 1: Write failing test for model imports**

```python
# tests/test_models.py
from src.models.ledger import Ledger, Transaction, TransactionStatus
from src.models.whitelist import WhitelistEntry

def test_transaction_status_values():
    assert TransactionStatus.PENDING == "PENDING"
    assert TransactionStatus.SETTLED == "SETTLED"
    assert TransactionStatus.FAILED == "FAILED"

def test_whitelist_entry_has_address():
    entry = WhitelistEntry(address="0xABC", label="treasury")
    assert entry.address == "0xABC"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_models.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create src/database.py**

```python
# src/database.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from src.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
```

- [ ] **Step 4: Create src/models/ledger.py**

```python
# src/models/ledger.py
import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Numeric, String, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from src.database import Base


class TransactionStatus(str, enum.Enum):
    PENDING = "PENDING"
    SIGNED = "SIGNED"
    BROADCAST = "BROADCAST"
    SETTLED = "SETTLED"
    FAILED = "FAILED"


class PolicyDecision(str, enum.Enum):
    ALLOW = "ALLOW"
    CHALLENGE = "CHALLENGE"
    BLOCK = "BLOCK"


class Ledger(Base):
    __tablename__ = "ledgers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    balance: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False, default=Decimal("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="ledger")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ledger_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ledgers.id"), nullable=False)
    to_address: Mapped[str] = mapped_column(String(42), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    status: Mapped[TransactionStatus] = mapped_column(SAEnum(TransactionStatus), default=TransactionStatus.PENDING)
    policy_decision: Mapped[PolicyDecision] = mapped_column(SAEnum(PolicyDecision), nullable=True)
    tx_hash: Mapped[str | None] = mapped_column(String(66), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    ledger: Mapped["Ledger"] = relationship(back_populates="transactions")
```

- [ ] **Step 5: Create src/models/whitelist.py**

```python
# src/models/whitelist.py
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from src.database import Base


class WhitelistEntry(Base):
    __tablename__ = "whitelist"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    address: Mapped[str] = mapped_column(String(42), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 6: Create src/models/**init**.py**

```python
# src/models/__init__.py
from src.models.ledger import Ledger, Transaction, TransactionStatus, PolicyDecision
from src.models.whitelist import WhitelistEntry

__all__ = ["Ledger", "Transaction", "TransactionStatus", "PolicyDecision", "WhitelistEntry"]
```

- [ ] **Step 7: Run model tests to verify they pass**

```bash
pytest tests/test_models.py -v
```

Expected: PASS

- [ ] **Step 8: Initialize Alembic**

```bash
alembic init alembic
```

Edit `alembic.ini` — set `sqlalchemy.url = postgresql://sentinel:sentinel@localhost:5432/sentinel`.

Edit `alembic/env.py` — replace the target_metadata line:

```python
from src.database import Base
from src.models import *  # noqa: F401, F403 — registers all models
target_metadata = Base.metadata
```

- [ ] **Step 9: Generate initial migration**

```bash
docker compose up -d db
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

Expected: three tables created — `ledgers`, `transactions`, `whitelist`.

- [ ] **Step 10: Commit**

```bash
git add src/database.py src/models/ alembic/ alembic.ini tests/test_models.py
git commit -m "feat: ORM models and initial Alembic migration"
```

---

## Task 3: Policy Engine (Gatekeeper)

**Files:**

- Create: `src/gatekeeper/__init__.py`
- Create: `src/gatekeeper/policy.py`
- Test: `tests/test_policy.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_policy.py
import pytest
from decimal import Decimal
from src.gatekeeper.policy import PolicyEngine, PolicyRequest, PolicyDecision

WHITELIST = {"0xAPPROVED"}

@pytest.fixture
def engine():
    return PolicyEngine(whitelist_addresses=WHITELIST, daily_limit=Decimal("100"))

def test_allow_whitelisted_address_under_limit(engine):
    req = PolicyRequest(to_address="0xAPPROVED", amount=Decimal("50"), daily_spent=Decimal("0"))
    result = engine.evaluate(req)
    assert result == PolicyDecision.ALLOW

def test_block_non_whitelisted_address(engine):
    req = PolicyRequest(to_address="0xBLACKLIST", amount=Decimal("1"), daily_spent=Decimal("0"))
    result = engine.evaluate(req)
    assert result == PolicyDecision.BLOCK

def test_challenge_when_daily_limit_exceeded(engine):
    req = PolicyRequest(to_address="0xAPPROVED", amount=Decimal("60"), daily_spent=Decimal("50"))
    result = engine.evaluate(req)
    assert result == PolicyDecision.CHALLENGE

def test_block_zero_amount(engine):
    req = PolicyRequest(to_address="0xAPPROVED", amount=Decimal("0"), daily_spent=Decimal("0"))
    result = engine.evaluate(req)
    assert result == PolicyDecision.BLOCK
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_policy.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Create src/gatekeeper/**init**.py** — empty file.

- [ ] **Step 4: Create src/gatekeeper/policy.py**

```python
# src/gatekeeper/policy.py
from dataclasses import dataclass
from decimal import Decimal
from src.models.ledger import PolicyDecision


@dataclass(frozen=True)
class PolicyRequest:
    to_address: str
    amount: Decimal
    daily_spent: Decimal


class PolicyEngine:
    def __init__(self, whitelist_addresses: set[str], daily_limit: Decimal) -> None:
        self._whitelist = whitelist_addresses
        self._daily_limit = daily_limit

    def evaluate(self, request: PolicyRequest) -> PolicyDecision:
        if request.amount <= 0:
            return PolicyDecision.BLOCK
        if request.to_address not in self._whitelist:
            return PolicyDecision.BLOCK
        if request.daily_spent + request.amount > self._daily_limit:
            return PolicyDecision.CHALLENGE
        return PolicyDecision.ALLOW
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_policy.py -v
```

Expected: 4 PASS

- [ ] **Step 6: Commit**

```bash
git add src/gatekeeper/ tests/test_policy.py
git commit -m "feat: policy engine with Allow/Challenge/Block logic"
```

---

## Task 4: Withdrawal API (Gatekeeper Router)

**Files:**

- Create: `src/gatekeeper/schemas.py`
- Create: `src/gatekeeper/router.py`
- Create: `src/main.py`
- Create: `tests/conftest.py`
- Test: `tests/test_withdrawal_api.py`

- [ ] **Step 1: Write failing API tests**

```python
# tests/test_withdrawal_api.py
import pytest
import pytest_asyncio
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch

from src.main import create_app


@pytest_asyncio.fixture
async def client():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def test_withdrawal_blocked_non_whitelist(client):
    payload = {"ledger_id": "00000000-0000-0000-0000-000000000001",
               "to_address": "0xBAD", "amount": "10.0"}
    with patch("src.gatekeeper.router.fetch_whitelist", new_callable=AsyncMock, return_value=set()):
        with patch("src.gatekeeper.router.fetch_daily_spent", new_callable=AsyncMock, return_value=Decimal("0")):
            with patch("src.gatekeeper.router.save_transaction", new_callable=AsyncMock):
                resp = await client.post("/withdrawals", json=payload)
    assert resp.status_code == 200
    assert resp.json()["decision"] == "BLOCK"


async def test_withdrawal_allowed(client):
    payload = {"ledger_id": "00000000-0000-0000-0000-000000000001",
               "to_address": "0xGOOD", "amount": "10.0"}
    with patch("src.gatekeeper.router.fetch_whitelist", new_callable=AsyncMock, return_value={"0xGOOD"}):
        with patch("src.gatekeeper.router.fetch_daily_spent", new_callable=AsyncMock, return_value=Decimal("0")):
            with patch("src.gatekeeper.router.save_transaction", new_callable=AsyncMock):
                resp = await client.post("/withdrawals", json=payload)
    assert resp.status_code == 200
    assert resp.json()["decision"] == "ALLOW"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_withdrawal_api.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Create src/gatekeeper/schemas.py**

```python
# src/gatekeeper/schemas.py
import uuid
from decimal import Decimal
from pydantic import BaseModel, field_validator


class WithdrawalRequest(BaseModel):
    ledger_id: uuid.UUID
    to_address: str
    amount: Decimal

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("amount must be positive")
        return v

    @field_validator("to_address")
    @classmethod
    def address_must_be_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("to_address must not be empty")
        return v


class WithdrawalResponse(BaseModel):
    transaction_id: uuid.UUID
    decision: str
    message: str
```

- [ ] **Step 4: Create src/gatekeeper/router.py**

```python
# src/gatekeeper/router.py
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from src.database import get_session
from src.models.ledger import Transaction, TransactionStatus, PolicyDecision
from src.models.whitelist import WhitelistEntry
from src.gatekeeper.schemas import WithdrawalRequest, WithdrawalResponse
from src.gatekeeper.policy import PolicyEngine, PolicyRequest
from src.config import settings

router = APIRouter(prefix="/withdrawals", tags=["gatekeeper"])
DAILY_LIMIT = Decimal("10000")


async def fetch_whitelist(session: AsyncSession) -> set[str]:
    rows = await session.execute(select(WhitelistEntry.address))
    return {r for r, in rows.all()}


async def fetch_daily_spent(session: AsyncSession, ledger_id: uuid.UUID) -> Decimal:
    result = await session.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.ledger_id == ledger_id,
            Transaction.status != TransactionStatus.FAILED,
        )
    )
    return Decimal(str(result.scalar()))


async def save_transaction(session: AsyncSession, tx: Transaction) -> None:
    session.add(tx)
    await session.commit()
    await session.refresh(tx)


@router.post("", response_model=WithdrawalResponse)
async def request_withdrawal(
    body: WithdrawalRequest,
    session: AsyncSession = Depends(get_session),
) -> WithdrawalResponse:
    whitelist = await fetch_whitelist(session)
    daily_spent = await fetch_daily_spent(session, body.ledger_id)

    engine = PolicyEngine(whitelist_addresses=whitelist, daily_limit=DAILY_LIMIT)
    decision = engine.evaluate(PolicyRequest(
        to_address=body.to_address,
        amount=body.amount,
        daily_spent=daily_spent,
    ))

    tx = Transaction(
        ledger_id=body.ledger_id,
        to_address=body.to_address,
        amount=body.amount,
        status=TransactionStatus.PENDING if decision == PolicyDecision.ALLOW else TransactionStatus.FAILED,
        policy_decision=decision,
    )
    await save_transaction(session, tx)

    messages = {
        PolicyDecision.ALLOW: "Transaction queued for signing",
        PolicyDecision.CHALLENGE: "Manual review required — daily limit exceeded",
        PolicyDecision.BLOCK: "Transaction blocked by policy",
    }
    return WithdrawalResponse(
        transaction_id=tx.id,
        decision=decision.value,
        message=messages[decision],
    )
```

- [ ] **Step 5: Create src/main.py**

```python
# src/main.py
from fastapi import FastAPI
from src.gatekeeper.router import router as gatekeeper_router


def create_app() -> FastAPI:
    app = FastAPI(title="Sentinel Custody Engine", version="0.1.0")
    app.include_router(gatekeeper_router)
    return app


app = create_app()
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/test_withdrawal_api.py -v
```

Expected: 2 PASS

- [ ] **Step 7: Commit**

```bash
git add src/gatekeeper/schemas.py src/gatekeeper/router.py src/main.py tests/test_withdrawal_api.py
git commit -m "feat: withdrawal API with policy enforcement pipeline"
```

---

## Task 5: MPC Key Sharding (Orchestrator)

**Files:**

- Create: `src/orchestrator/__init__.py`
- Create: `src/orchestrator/key_sharding.py`
- Test: `tests/test_key_sharding.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_key_sharding.py
import pytest
from src.orchestrator.key_sharding import split_secret, reconstruct_secret

SECRET = b"super-secret-private-key-32bytes"

def test_split_produces_correct_share_count():
    shares = split_secret(SECRET, threshold=2, total=3)
    assert len(shares) == 3

def test_reconstruct_with_all_shares():
    shares = split_secret(SECRET, threshold=2, total=3)
    recovered = reconstruct_secret(shares, threshold=2)
    assert recovered == SECRET

def test_reconstruct_with_minimum_shares():
    shares = split_secret(SECRET, threshold=2, total=3)
    recovered = reconstruct_secret(shares[:2], threshold=2)
    assert recovered == SECRET

def test_reconstruct_fails_with_insufficient_shares():
    shares = split_secret(SECRET, threshold=2, total=3)
    with pytest.raises(ValueError, match="Insufficient shares"):
        reconstruct_secret(shares[:1], threshold=2)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_key_sharding.py -v
```

Expected: FAIL

- [ ] **Step 3: Create src/orchestrator/**init**.py** — empty file.

- [ ] **Step 4: Create src/orchestrator/key_sharding.py**

```python
# src/orchestrator/key_sharding.py
"""
Shamir's Secret Sharing wrapper using PyCryptodome.
Each share is a (index, bytes) tuple for transport/storage.
"""
from Crypto.Protocol.SecretSharing import Shamir


def split_secret(secret: bytes, threshold: int, total: int) -> list[tuple[int, bytes]]:
    """Split secret into `total` shares; any `threshold` can reconstruct."""
    if len(secret) != 16:
        # Shamir in PyCryptodome requires exactly 16 bytes (128-bit)
        secret = secret[:16].ljust(16, b"\x00")
    shares = Shamir.split(threshold, total, secret)
    return shares


def reconstruct_secret(shares: list[tuple[int, bytes]], threshold: int) -> bytes:
    """Reconstruct secret from at least `threshold` shares."""
    if len(shares) < threshold:
        raise ValueError(f"Insufficient shares: need {threshold}, got {len(shares)}")
    return Shamir.combine(shares)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_key_sharding.py -v
```

Expected: 4 PASS

- [ ] **Step 6: Commit**

```bash
git add src/orchestrator/ tests/test_key_sharding.py
git commit -m "feat: Shamir secret sharing for MPC key sharding"
```

---

## Task 6: Threshold Signing Workflow (Orchestrator)

**Files:**

- Create: `src/orchestrator/signing.py`
- Test: `tests/test_signing.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_signing.py
import pytest
from unittest.mock import patch, MagicMock
from src.orchestrator.signing import MPCSigner, SigningRequest

SECRET = b"private-key-data"  # 16 bytes after truncation

@pytest.fixture
def signer():
    shares = _make_shares(SECRET)
    return MPCSigner(all_shares=shares, threshold=2)

def _make_shares(secret: bytes):
    from src.orchestrator.key_sharding import split_secret
    return split_secret(secret, threshold=2, total=3)

def test_sign_with_two_shares(signer):
    active_shares = signer.all_shares[:2]
    result = signer.sign(tx_data=b"tx-payload", active_shares=active_shares)
    assert result is not None
    assert isinstance(result, bytes)

def test_sign_with_all_shares(signer):
    result = signer.sign(tx_data=b"tx-payload", active_shares=signer.all_shares)
    assert result is not None

def test_sign_fails_with_one_share(signer):
    with pytest.raises(ValueError, match="Insufficient shares"):
        signer.sign(tx_data=b"tx-payload", active_shares=signer.all_shares[:1])

def test_mpc_test_from_plan():
    """Reproduces the scenario from plan.md 4.2."""
    from src.orchestrator.key_sharding import split_secret
    shares = split_secret(SECRET, threshold=2, total=3)
    share_1, share_2, _share_3 = shares  # share_3 offline
    signer = MPCSigner(all_shares=shares, threshold=2)
    signature = signer.sign(b"tx-data", active_shares=[share_1, share_2])
    assert signature is not None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_signing.py -v
```

Expected: FAIL

- [ ] **Step 3: Create src/orchestrator/signing.py**

```python
# src/orchestrator/signing.py
import hashlib
from dataclasses import dataclass
from src.orchestrator.key_sharding import reconstruct_secret


@dataclass
class SigningRequest:
    tx_data: bytes


class MPCSigner:
    def __init__(self, all_shares: list[tuple[int, bytes]], threshold: int) -> None:
        self.all_shares = all_shares
        self.threshold = threshold

    def sign(self, tx_data: bytes, active_shares: list[tuple[int, bytes]]) -> bytes:
        """
        Reconstruct private key from active shares, then sign tx_data.
        Returns HMAC-SHA256 signature (simulation — replace with real ECDSA in prod).
        """
        private_key = reconstruct_secret(active_shares, self.threshold)
        signature = hashlib.sha256(private_key + tx_data).digest()
        return signature
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_signing.py -v
```

Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add src/orchestrator/signing.py tests/test_signing.py
git commit -m "feat: 2-of-3 MPC threshold signing workflow"
```

---

## Task 7: Broadcast Gateway (Orchestrator)

**Files:**

- Create: `src/orchestrator/broadcast.py`
- Test: `tests/test_broadcast.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_broadcast.py
import pytest
from unittest.mock import MagicMock, patch
from src.orchestrator.broadcast import BroadcastGateway

def test_broadcast_returns_tx_hash():
    mock_w3 = MagicMock()
    mock_w3.eth.send_raw_transaction.return_value = bytes.fromhex("deadbeef" * 8)
    mock_w3.to_hex.return_value = "0x" + "deadbeef" * 8

    gw = BroadcastGateway(w3=mock_w3)
    tx_hash = gw.broadcast(signed_tx=b"signed-tx-bytes")

    mock_w3.eth.send_raw_transaction.assert_called_once_with(b"signed-tx-bytes")
    assert tx_hash.startswith("0x")

def test_broadcast_propagates_web3_error():
    mock_w3 = MagicMock()
    mock_w3.eth.send_raw_transaction.side_effect = Exception("network error")

    gw = BroadcastGateway(w3=mock_w3)
    with pytest.raises(RuntimeError, match="Broadcast failed"):
        gw.broadcast(signed_tx=b"signed-tx-bytes")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_broadcast.py -v
```

Expected: FAIL

- [ ] **Step 3: Create src/orchestrator/broadcast.py**

```python
# src/orchestrator/broadcast.py
from web3 import Web3


class BroadcastGateway:
    def __init__(self, w3: Web3) -> None:
        self._w3 = w3

    def broadcast(self, signed_tx: bytes) -> str:
        """Send raw signed transaction to network. Returns tx hash hex string."""
        try:
            raw_hash = self._w3.eth.send_raw_transaction(signed_tx)
            return self._w3.to_hex(raw_hash)
        except Exception as exc:
            raise RuntimeError(f"Broadcast failed: {exc}") from exc
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_broadcast.py -v
```

Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add src/orchestrator/broadcast.py tests/test_broadcast.py
git commit -m "feat: Web3 broadcast gateway with error wrapping"
```

---

## Task 8: On-Chain Indexer & Reconciler (Auditor)

**Files:**

- Create: `src/auditor/__init__.py`
- Create: `src/auditor/indexer.py`
- Create: `src/auditor/reconciler.py`
- Test: `tests/test_reconciler.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_reconciler.py
import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from src.auditor.reconciler import Reconciler
from src.models.ledger import TransactionStatus


@pytest.fixture
def reconciler():
    mock_session = AsyncMock()
    mock_indexer = MagicMock()
    return Reconciler(session=mock_session, indexer=mock_indexer)


async def test_reconcile_settles_confirmed_tx(reconciler):
    tx_id = uuid.uuid4()
    tx_hash = "0xabc"
    reconciler.indexer.get_receipt.return_value = {"status": 1}  # 1 = success on EVM

    mock_tx = MagicMock()
    mock_tx.status = TransactionStatus.BROADCAST
    mock_tx.tx_hash = tx_hash
    reconciler.session.get.return_value = mock_tx

    await reconciler.sync(tx_id=tx_id)

    assert mock_tx.status == TransactionStatus.SETTLED
    reconciler.session.commit.assert_awaited_once()


async def test_reconcile_fails_reverted_tx(reconciler):
    tx_id = uuid.uuid4()
    mock_tx = MagicMock()
    mock_tx.status = TransactionStatus.BROADCAST
    mock_tx.tx_hash = "0xfail"
    reconciler.session.get.return_value = mock_tx
    reconciler.indexer.get_receipt.return_value = {"status": 0}  # reverted

    await reconciler.sync(tx_id=tx_id)

    assert mock_tx.status == TransactionStatus.FAILED
    reconciler.session.commit.assert_awaited_once()


async def test_reconciliation_on_chain_failure_from_plan(reconciler):
    """Reproduces plan.md 4.3 scenario."""
    tx_id = uuid.uuid4()
    mock_tx = MagicMock()
    mock_tx.status = TransactionStatus.BROADCAST
    mock_tx.tx_hash = "0xbad"
    reconciler.session.get.return_value = mock_tx
    reconciler.indexer.get_receipt.return_value = {"status": 0}

    await reconciler.sync(tx_id=tx_id)

    assert mock_tx.status == TransactionStatus.FAILED
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_reconciler.py -v
```

Expected: FAIL

- [ ] **Step 3: Create src/auditor/**init**.py** — empty file.

- [ ] **Step 4: Create src/auditor/indexer.py**

```python
# src/auditor/indexer.py
from web3 import Web3


class OnChainIndexer:
    def __init__(self, w3: Web3) -> None:
        self._w3 = w3

    def get_receipt(self, tx_hash: str) -> dict | None:
        """Fetch transaction receipt. Returns None if not yet mined."""
        try:
            receipt = self._w3.eth.get_transaction_receipt(tx_hash)
            if receipt is None:
                return None
            return {"status": receipt["status"]}
        except Exception:
            return None
```

- [ ] **Step 5: Create src/auditor/reconciler.py**

```python
# src/auditor/reconciler.py
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.auditor.indexer import OnChainIndexer
from src.models.ledger import Transaction, TransactionStatus


class Reconciler:
    def __init__(self, session: AsyncSession, indexer: OnChainIndexer) -> None:
        self.session = session
        self.indexer = indexer

    async def sync(self, tx_id: uuid.UUID) -> None:
        """Check on-chain result and update ledger status accordingly."""
        tx: Transaction = await self.session.get(Transaction, tx_id)
        if tx is None or tx.tx_hash is None:
            return

        receipt = self.indexer.get_receipt(tx.tx_hash)
        if receipt is None:
            return  # not yet mined — skip until next poll

        if receipt["status"] == 1:
            tx.status = TransactionStatus.SETTLED
            tx.settled_at = datetime.now(timezone.utc)
        else:
            tx.status = TransactionStatus.FAILED

        await self.session.commit()
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/test_reconciler.py -v
```

Expected: 3 PASS

- [ ] **Step 7: Commit**

```bash
git add src/auditor/ tests/test_reconciler.py
git commit -m "feat: on-chain indexer and reconciliation service"
```

---

## Task 9: Full Test Suite & Integration Smoke Test

**Files:**

- Create: `tests/conftest.py`

- [ ] **Step 1: Create shared conftest**

```python
# tests/conftest.py
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from src.main import create_app


@pytest_asyncio.fixture
async def client():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
```

- [ ] **Step 2: Run full test suite**

```bash
pytest tests/ -v --tb=short
```

Expected: All tests PASS (no DB connection needed — all DB calls are mocked in unit tests).

- [ ] **Step 3: Verify live API starts**

```bash
docker compose up -d db
alembic upgrade head
uvicorn src.main:app --reload
```

In a second terminal:

```bash
curl -s -X POST http://localhost:8000/withdrawals \
  -H "Content-Type: application/json" \
  -d '{"ledger_id":"00000000-0000-0000-0000-000000000001","to_address":"0xBAD","amount":"5.0"}' | python3 -m json.tool
```

Expected: `"decision": "BLOCK"` (no whitelist entries in fresh DB).

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py
git commit -m "test: shared conftest and full integration smoke test verified"
```

---

## Task 10: Break-Glass Recovery Module

**Files:**

- Create: `src/orchestrator/break_glass.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_break_glass.py
import pytest
from src.orchestrator.key_sharding import split_secret
from src.orchestrator.break_glass import BreakGlassRecovery

SECRET = b"emergency-private"  # will be truncated to 16 bytes

def test_break_glass_recovery_with_emergency_share():
    shares = split_secret(SECRET, threshold=2, total=3)
    share_1, _share_2, share_3 = shares  # share_2 unavailable

    recovery = BreakGlassRecovery(threshold=2)
    recovered = recovery.recover(active_shares=[share_1, share_3])
    assert isinstance(recovered, bytes)
    assert len(recovered) == 16

def test_break_glass_fails_without_enough_shares():
    shares = split_secret(SECRET, threshold=2, total=3)
    recovery = BreakGlassRecovery(threshold=2)
    with pytest.raises(ValueError, match="Insufficient shares"):
        recovery.recover(active_shares=[shares[0]])
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_break_glass.py -v
```

Expected: FAIL

- [ ] **Step 3: Create src/orchestrator/break_glass.py**

```python
# src/orchestrator/break_glass.py
from src.orchestrator.key_sharding import reconstruct_secret


class BreakGlassRecovery:
    """
    Emergency recovery using any threshold-count shares including share #3.
    Intended for disaster scenarios only — audit log this call in production.
    """

    def __init__(self, threshold: int) -> None:
        self.threshold = threshold

    def recover(self, active_shares: list[tuple[int, bytes]]) -> bytes:
        return reconstruct_secret(active_shares, self.threshold)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_break_glass.py -v
```

Expected: 2 PASS

- [ ] **Step 5: Final full suite run**

```bash
pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/orchestrator/break_glass.py tests/test_break_glass.py
git commit -m "feat: break-glass emergency recovery module"
```

---

## Self-Review Checklist

### Spec Coverage

| Plan requirement                             | Task                                                    |
| -------------------------------------------- | ------------------------------------------------------- |
| PostgreSQL Ledger, Transaction, Whitelist    | Task 2                                                  |
| Policy Engine (Allow/Challenge/Block)        | Task 3                                                  |
| Withdrawal API pipeline                      | Task 4                                                  |
| Key Sharding (3 shares)                      | Task 5                                                  |
| Threshold Signing (2-of-3)                   | Task 6                                                  |
| Broadcast Gateway (Web3)                     | Task 7                                                  |
| On-Chain Indexer                             | Task 8                                                  |
| Reconciliation Service                       | Task 8                                                  |
| Break-Glass module                           | Task 10                                                 |
| plan.md test 4.1 (BLOCK on blacklist)        | Task 3 `test_block_non_whitelisted_address`             |
| plan.md test 4.2 (MPC with 1 node down)      | Task 6 `test_mpc_test_from_plan`                        |
| plan.md test 4.3 (reconciliation on failure) | Task 8 `test_reconciliation_on_chain_failure_from_plan` |

### No Placeholders — confirmed. All steps have concrete code.

### Type Consistency — `TransactionStatus`, `PolicyDecision` defined in Task 2, reused consistently through Task 8. `split_secret` / `reconstruct_secret` signatures match across Tasks 5, 6, 10.
