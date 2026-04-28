# Sentinel Custody Engine

FastAPI crypto custody withdrawal engine. Accepts withdrawal requests, enforces policy, signs Ethereum transactions via simulated MPC, broadcasts to Sepolia testnet, and reconciles on-chain receipts back to the DB with full audit logs.

## What It Does

- API key protected withdrawal API
- Whitelist and daily withdrawal limit policy checks
- Transaction lifecycle:
  - `ALLOW` → `PENDING` → `SIGNED` → `BROADCAST` → `SETTLED`
  - `CHALLENGE` → `PENDING_REVIEW` → (approve) `PENDING` or (reject) `FAILED`
  - `BLOCK` → `FAILED`
- PostgreSQL ledger, transaction, whitelist, and audit log tables
- Ethereum EIP-1559 tx building, `eth-account` signing, Web3 broadcast, receipt reconciliation
- Three local Postgres services:
  - `db` — dev DB on `localhost:5433`
  - `db-test` — clean test DB on `localhost:5434`
  - `db-record` — persistent demo/audit DB on `localhost:5435`
- Web UI at three routes (no auth required):
  - `/dashboard` — live admin: transactions, ledgers, whitelist, action buttons
  - `/multidb` — side-by-side view of all three databases (dev / test / record)
  - `/audit` — paginated per-transaction audit timeline (5 tx/page, newest-first)

## Local Setup

```bash
pip install -e ".[dev]"
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
DATABASE_URL_TEST=postgresql+asyncpg://sentinel:sentinel@localhost:5434/sentinel_test
DATABASE_URL_RECORD=postgresql+asyncpg://sentinel:sentinel@localhost:5435/sentinel_record
```

Apply migrations to all three DBs:

```bash
python -m alembic upgrade head
DATABASE_URL=postgresql+asyncpg://sentinel:sentinel@localhost:5434/sentinel_test python -m alembic upgrade head
DATABASE_URL=postgresql+asyncpg://sentinel:sentinel@localhost:5435/sentinel_record python -m alembic upgrade head
```

Start server:

```bash
python -m uvicorn src.main:app --reload
```

Open in browser:

```bash
# Dashboard (live admin panel)
open http://localhost:8000/dashboard

# Multi-DB view (all three databases side-by-side)
open http://localhost:8000/multidb

# Audit logs (per-transaction timeline, paginated)
open http://localhost:8000/audit
```

Never commit `.env` or private keys. Use a Sepolia-only test wallet.

## Demo Reset

Seed 10 demo transactions into the dev DB (resets any existing data):

```bash
python scripts/reset_demo.py
```

Then refresh your browser (dashboard auto-polls every 5 seconds).

Seeded state:

| ID prefix | Amount                | Policy    | Status                                           |
| --------- | --------------------- | --------- | ------------------------------------------------ |
| 1ce706e3  | 1 wei (self-transfer) | ALLOW     | PENDING → hit PROCESS for real Sepolia broadcast |
| c3fde654  | 100 ETH               | ALLOW     | PENDING                                          |
| 253b33ff  | 200 ETH               | ALLOW     | PENDING                                          |
| 9e703c17  | 9800 ETH              | CHALLENGE | PENDING_REVIEW                                   |
| b10c0000  | 50000 ETH             | BLOCK     | FAILED                                           |
| aa000001  | 500 ETH               | ALLOW     | SETTLED (full lifecycle example)                 |
| aa000002  | 75 ETH                | ALLOW     | BROADCAST                                        |
| aa000003  | 1500 ETH              | CHALLENGE | PENDING_REVIEW                                   |
| aa000004  | 10 ETH                | ALLOW     | FAILED                                           |
| aa000005  | 1 ETH                 | ALLOW     | SIGNED                                           |

---

## Tests

```bash
# Default suite (no real broadcast)
python -m pytest -q
```

Expected: `60 passed, 2 skipped`

```bash
# Skip broadcast tests explicitly
python -m pytest -q -m "not sepolia_broadcast"
```

Expected: `60 passed, 2 deselected`

```bash
# Read-only Sepolia RPC tests
python -m pytest tests/test_web3_rpc_integration.py -q
```

Expected: `2 passed, 60 deselected`

```bash
# Real Sepolia broadcast (sends 1 wei, costs testnet gas)
RUN_SEPOLIA_BROADCAST=1 python -m pytest -q -m sepolia_broadcast -s
```

Expected: `2 passed, 60 deselected`

---

## API Reference

All endpoints require `X-API-Key: my-local-test-key` header.

### Transactions

```bash
# Create withdrawal
curl -X POST http://127.0.0.1:8000/withdrawals \
  -H "Content-Type: application/json" \
  -H "X-API-Key: my-local-test-key" \
  -d '{"ledger_id": "00000000-0000-0000-0000-000000000001", "to_address": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "amount": "10.0"}'

# List transactions (last 50)
curl http://127.0.0.1:8000/withdrawals?limit=50 \
  -H "X-API-Key: my-local-test-key"

# Get transaction status
curl http://127.0.0.1:8000/withdrawals/TRANSACTION_ID \
  -H "X-API-Key: my-local-test-key"

# Get audit logs for a transaction
curl http://127.0.0.1:8000/withdrawals/TRANSACTION_ID/audit-logs \
  -H "X-API-Key: my-local-test-key"
```

### Transaction Actions

```bash
# Approve (PENDING_REVIEW → PENDING)
curl -X POST http://127.0.0.1:8000/withdrawals/TRANSACTION_ID/approve \
  -H "X-API-Key: my-local-test-key"

# Reject (PENDING_REVIEW → FAILED)
curl -X POST http://127.0.0.1:8000/withdrawals/TRANSACTION_ID/reject \
  -H "X-API-Key: my-local-test-key"

# Process next PENDING transaction
curl -X POST http://127.0.0.1:8000/withdrawals/process-next \
  -H "X-API-Key: my-local-test-key"

# Process specific transaction
curl -X POST http://127.0.0.1:8000/withdrawals/TRANSACTION_ID/process \
  -H "X-API-Key: my-local-test-key"

# Reconcile broadcast transaction (fetch on-chain receipt)
curl -X POST http://127.0.0.1:8000/transactions/TRANSACTION_ID/reconcile \
  -H "X-API-Key: my-local-test-key"
```

### Admin / Reporting

```bash
# Ledgers
curl http://127.0.0.1:8000/ledgers \
  -H "X-API-Key: my-local-test-key"

# Whitelist
curl http://127.0.0.1:8000/whitelist \
  -H "X-API-Key: my-local-test-key"

# Stats
curl http://127.0.0.1:8000/stats \
  -H "X-API-Key: my-local-test-key"

# All transactions + audit logs from all 3 databases
curl http://127.0.0.1:8000/multi-db \
  -H "X-API-Key: my-local-test-key"

# All transactions with full audit timelines (10 tx/endpoint, paginated in UI)
curl http://127.0.0.1:8000/withdrawals/audit-all \
  -H "X-API-Key: my-local-test-key"
```

### Whitelist Management

```bash
# Add address to whitelist
curl -X POST http://127.0.0.1:8000/whitelist \
  -H "Content-Type: application/json" \
  -H "X-API-Key: my-local-test-key" \
  -d '{"address": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "label": "Cold Storage"}'

# Remove from whitelist
curl -X DELETE http://127.0.0.1:8000/whitelist/0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \
  -H "X-API-Key: my-local-test-key"
```

## DB Inspection

```bash
docker compose exec db      psql -U sentinel -d sentinel
docker compose exec db-test psql -U sentinel -d sentinel_test
docker compose exec db-record psql -U sentinel -d sentinel_record
```

```sql
SELECT id, to_address, amount, status, policy_decision, tx_hash, settled_at
FROM transactions ORDER BY created_at DESC;

SELECT transaction_id, event_type, status, tx_hash, message, created_at
FROM transaction_audit_logs ORDER BY created_at DESC;
```

## Notes

- Real broadcast tests opt-in via `RUN_SEPOLIA_BROADCAST=1`
- DB timestamps stored UTC; displayed in `America/Los_Angeles` in the web UI
- `STUDY.md` is intentionally gitignored — personal long-form notes
