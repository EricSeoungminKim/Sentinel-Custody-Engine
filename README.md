# Sentinel Custody Engine

FastAPI prototype for a crypto custody withdrawal engine. It accepts withdrawal requests, checks policy, records ledger state in PostgreSQL, signs Ethereum transactions, broadcasts to Sepolia when explicitly requested, and reconciles receipts back into DB status/audit logs.

## What It Does

- API key protected withdrawal API.
- Whitelist and daily withdrawal limit policy checks.
- Transaction status lifecycle:
  - `ALLOW` -> `PENDING`
  - `CHALLENGE` -> `PENDING_REVIEW`
  - `BLOCK` -> `FAILED`
  - processed `PENDING` -> `SIGNED` -> `BROADCAST` -> `SETTLED`
- PostgreSQL ledger, transaction, whitelist, and audit log tables.
- Ethereum EIP-1559 transaction building, `eth-account` signing, Web3 broadcast, receipt reconciliation.
- Three local Postgres services:
  - `db`: local dev DB on `localhost:5433`
  - `db-test`: clean test DB on `localhost:5434`
  - `db-record`: persistent demo/audit DB on `localhost:5435`

## Overall Workflow

```text
POST /withdrawals
-> API key auth
-> whitelist + daily limit policy
-> transaction row saved
-> optional manual approve/reject
-> worker builds Ethereum tx
-> signer creates raw transaction
-> broadcaster submits raw tx to Sepolia
-> tx_hash saved
-> reconciler reads receipt
-> status becomes SETTLED or FAILED
-> audit log records SIGNED/BROADCAST/SETTLED/FAILED
```

## Local Setup

```bash
cd /Users/smk/Documents/GitHub/Sentinel-Custody-Engine/.worktrees/feature/build
python -m pip install -e ".[dev]"
docker compose up -d db db-test db-record
```

Create `.env`:

```env
DATABASE_URL=postgresql+asyncpg://sentinel:sentinel@localhost:5433/sentinel
WEB3_RPC_URL=https://sepolia.infura.io/v3/YOUR_API_KEY
SENTINEL_API_KEY=my-local-test-key
SEPOLIA_TEST_PRIVATE_KEY=0xYOUR_TEST_WALLET_PRIVATE_KEY
MPC_MIN_SHARES=2
MPC_TOTAL_SHARES=3
DAILY_WITHDRAWAL_LIMIT=10000
```

Apply migrations:

```bash
python -m alembic upgrade head
DATABASE_URL=postgresql+asyncpg://sentinel:sentinel@localhost:5434/sentinel_test python -m alembic upgrade head
DATABASE_URL=postgresql+asyncpg://sentinel:sentinel@localhost:5435/sentinel_record python -m alembic upgrade head
```

Never commit `.env` or private keys. Use a Sepolia-only test wallet.

## Test Commands

Default suite, no real Sepolia broadcast:

```bash
python -m pytest -q
```

Expected:

```text
58 passed, 2 skipped
```

Run all non-broadcast tests explicitly:

```bash
python -m pytest -q -m "not sepolia_broadcast"
```

Run read-only Sepolia RPC tests:

```bash
python -m pytest tests/test_web3_rpc_integration.py -q
```

Run real Sepolia broadcast tests. This sends 1 wei self-transfers and spends testnet gas:

```bash
RUN_SEPOLIA_BROADCAST=1 python -m pytest -q -m sepolia_broadcast -s
```

Run persistent record/demo flow against `db-record`:

```bash
DATABASE_URL=postgresql+asyncpg://sentinel:sentinel@localhost:5435/sentinel_record \
  python -m src.orchestrator.record_demo
```

Inspect DB:

```bash
docker compose exec db psql -U sentinel -d sentinel
docker compose exec db-test psql -U sentinel -d sentinel_test
docker compose exec db-record psql -U sentinel -d sentinel_record
```

Useful SQL:

```sql
select id, ledger_id, to_address, amount, status, policy_decision, tx_hash, settled_at
from transactions
order by created_at desc;

select transaction_id, event_type, status, tx_hash, message, created_at
from transaction_audit_logs
order by created_at desc;
```

## API Smoke Test

Run server:

```bash
python -m uvicorn src.main:app --reload
```

Create withdrawal:

```bash
curl -s -X POST http://127.0.0.1:8000/withdrawals \
  -H "Content-Type: application/json" \
  -H "X-API-Key: my-local-test-key" \
  -d '{
    "ledger_id": "00000000-0000-0000-0000-000000000001",
    "to_address": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "amount": "10.0"
  }' | python -m json.tool
```

Check status:

```bash
curl -s http://127.0.0.1:8000/withdrawals/TRANSACTION_ID \
  -H "X-API-Key: my-local-test-key" | python -m json.tool
```

Dashboard/admin endpoints:

```bash
curl -s http://127.0.0.1:8000/withdrawals \
  -H "X-API-Key: my-local-test-key" | python -m json.tool

curl -s http://127.0.0.1:8000/ledgers \
  -H "X-API-Key: my-local-test-key" | python -m json.tool

curl -s http://127.0.0.1:8000/stats \
  -H "X-API-Key: my-local-test-key" | python -m json.tool

curl -s http://127.0.0.1:8000/whitelist \
  -H "X-API-Key: my-local-test-key" | python -m json.tool
```

Review flow:

```bash
curl -s -X POST http://127.0.0.1:8000/withdrawals/TRANSACTION_ID/approve \
  -H "X-API-Key: my-local-test-key" | python -m json.tool

curl -s -X POST http://127.0.0.1:8000/withdrawals/TRANSACTION_ID/reject \
  -H "X-API-Key: my-local-test-key" | python -m json.tool
```

Process next pending transaction:

```bash
curl -s -X POST http://127.0.0.1:8000/withdrawals/process-next \
  -H "X-API-Key: my-local-test-key" | python -m json.tool
```

## Notes

- Real broadcast tests are opt-in with `RUN_SEPOLIA_BROADCAST=1`.
- DB timestamps are UTC. Convert with `at time zone 'America/Los_Angeles'` when needed.
- `STUDY.md` is intentionally ignored and contains personal long-form notes.
