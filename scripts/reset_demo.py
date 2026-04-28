"""Reset dev DB to the standard 10-transaction demo state.

Usage:
    python scripts/reset_demo.py

Transactions:
  1ce706e3  1 wei self-transfer      ALLOW      PENDING        → PROCESS (real Sepolia broadcast)
  c3fde654  100 ETH cold storage     ALLOW      PENDING        → PROCESS (will FAIL: insufficient funds)
  253b33ff  200 ETH partner wallet   ALLOW      PENDING        → PROCESS (will FAIL: insufficient funds)
  9e703c17  9800 ETH challenge       CHALLENGE  PENDING_REVIEW → APPROVE/REJECT
  b10c0000  50000 ETH blacklisted    BLOCK      FAILED
  aa000001  500 ETH cold storage     ALLOW      SETTLED        (full lifecycle example)
  aa000002  75 ETH partner wallet    ALLOW      BROADCAST
  aa000003  1500 ETH mid-size        CHALLENGE  PENDING_REVIEW
  aa000004  10 ETH cold storage      ALLOW      FAILED         (broadcast failed)
  aa000005  1 ETH partner wallet     ALLOW      SIGNED
"""

import asyncio
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV = dotenv_values(_PROJECT_ROOT / ".env")

DATABASE_URL = _ENV.get("DATABASE_URL", "postgresql+asyncpg://sentinel:sentinel@localhost:5433/sentinel")

SEED_SQL = """
DO $$
DECLARE
    ledger_id UUID;
BEGIN
    DELETE FROM transaction_audit_logs;
    DELETE FROM transactions;

    SELECT id INTO ledger_id FROM ledgers ORDER BY created_at LIMIT 1;
    IF ledger_id IS NULL THEN
        INSERT INTO ledgers (id, name, balance)
        VALUES (gen_random_uuid(), 'Demo Ledger', 0)
        RETURNING id INTO ledger_id;
    END IF;

    -- ── Original 5 ────────────────────────────────────────────────────────────

    -- 1 wei self-transfer (ALLOW / PENDING) — only sub-1-ETH case, wallet-to-wallet
    INSERT INTO transactions (id, ledger_id, to_address, amount, status, policy_decision, tx_hash, created_at)
    VALUES ('1ce706e3-40ca-46f1-9653-b8d3b67c70e6', ledger_id,
            '0xf1e3482B1f041464f98090dd5CF8d36b8Ae83EF1', 0.000000000000000001,
            'PENDING', 'ALLOW', NULL, now() - interval '30 minutes');

    -- 100 ETH cold storage (ALLOW / PENDING)
    INSERT INTO transactions (id, ledger_id, to_address, amount, status, policy_decision, tx_hash, created_at)
    VALUES ('c3fde654-fbdc-4b73-95dd-47735eed2503', ledger_id,
            '0xA000000000000000000000000000000000000001', 100.0,
            'PENDING', 'ALLOW', NULL, now() - interval '25 minutes');

    -- 200 ETH partner wallet (ALLOW / PENDING)
    INSERT INTO transactions (id, ledger_id, to_address, amount, status, policy_decision, tx_hash, created_at)
    VALUES ('253b33ff-e952-47a8-90a0-6c24840ce9a6', ledger_id,
            '0xB000000000000000000000000000000000000002', 200.0,
            'PENDING', 'ALLOW', NULL, now() - interval '20 minutes');

    -- 9800 ETH large withdrawal (CHALLENGE / PENDING_REVIEW)
    INSERT INTO transactions (id, ledger_id, to_address, amount, status, policy_decision, tx_hash, created_at)
    VALUES ('9e703c17-b6ba-4d13-9314-8c9f8515daeb', ledger_id,
            '0xA000000000000000000000000000000000000001', 9800.0,
            'PENDING_REVIEW', 'CHALLENGE', NULL, now() - interval '15 minutes');

    -- 50000 ETH blacklisted (BLOCK / FAILED)
    INSERT INTO transactions (id, ledger_id, to_address, amount, status, policy_decision, tx_hash, created_at)
    VALUES ('b10c0000-0000-0000-0000-000000000001', ledger_id,
            '0xC000000000000000000000000000000000000003', 50000.0,
            'FAILED', 'BLOCK', NULL, now() - interval '12 minutes');

    -- ── Extra 5 (varied lifecycle stages) ─────────────────────────────────────

    -- 500 ETH — full lifecycle: SETTLED
    INSERT INTO transactions (id, ledger_id, to_address, amount, status, policy_decision, tx_hash, created_at)
    VALUES ('aa000001-0000-0000-0000-000000000001', ledger_id,
            '0xA000000000000000000000000000000000000001', 500.0,
            'SETTLED', 'ALLOW',
            '0xdeadbeef00000000000000000000000000000000000000000000000000000001',
            now() - interval '10 minutes');

    -- 75 ETH — BROADCAST (awaiting confirmation)
    INSERT INTO transactions (id, ledger_id, to_address, amount, status, policy_decision, tx_hash, created_at)
    VALUES ('aa000002-0000-0000-0000-000000000002', ledger_id,
            '0xB000000000000000000000000000000000000002', 75.0,
            'BROADCAST', 'ALLOW',
            '0xdeadbeef00000000000000000000000000000000000000000000000000000002',
            now() - interval '8 minutes');

    -- 1500 ETH — CHALLENGE / PENDING_REVIEW
    INSERT INTO transactions (id, ledger_id, to_address, amount, status, policy_decision, tx_hash, created_at)
    VALUES ('aa000003-0000-0000-0000-000000000003', ledger_id,
            '0xC000000000000000000000000000000000000003', 1500.0,
            'PENDING_REVIEW', 'CHALLENGE', NULL, now() - interval '6 minutes');

    -- 10 ETH — FAILED broadcast
    INSERT INTO transactions (id, ledger_id, to_address, amount, status, policy_decision, tx_hash, created_at)
    VALUES ('aa000004-0000-0000-0000-000000000004', ledger_id,
            '0xA000000000000000000000000000000000000001', 10.0,
            'FAILED', 'ALLOW', NULL, now() - interval '4 minutes');

    -- 1 ETH — SIGNED (in-flight)
    INSERT INTO transactions (id, ledger_id, to_address, amount, status, policy_decision, tx_hash, created_at)
    VALUES ('aa000005-0000-0000-0000-000000000005', ledger_id,
            '0xB000000000000000000000000000000000000002', 1.0,
            'SIGNED', 'ALLOW', NULL, now() - interval '2 minutes');

    -- ── Audit logs ────────────────────────────────────────────────────────────

    INSERT INTO transaction_audit_logs (id, transaction_id, event_type, status, message, created_at)
    VALUES
        -- 1 wei self-transfer
        (gen_random_uuid(), '1ce706e3-40ca-46f1-9653-b8d3b67c70e6', 'CREATED', 'PENDING', '1 wei self-transfer queued', now() - interval '30 minutes'),

        -- 100 ETH
        (gen_random_uuid(), 'c3fde654-fbdc-4b73-95dd-47735eed2503', 'CREATED', 'PENDING', '100 ETH withdrawal queued', now() - interval '25 minutes'),

        -- 200 ETH
        (gen_random_uuid(), '253b33ff-e952-47a8-90a0-6c24840ce9a6', 'CREATED', 'PENDING', '200 ETH withdrawal queued', now() - interval '20 minutes'),

        -- 9800 ETH challenge
        (gen_random_uuid(), '9e703c17-b6ba-4d13-9314-8c9f8515daeb', 'CREATED', 'PENDING_REVIEW', '9800 ETH flagged for manual review', now() - interval '15 minutes'),

        -- 50000 ETH blocked
        (gen_random_uuid(), 'b10c0000-0000-0000-0000-000000000001', 'CREATED', 'FAILED', '50000 ETH to blacklisted address — blocked by policy', now() - interval '12 minutes'),

        -- 500 ETH full lifecycle
        (gen_random_uuid(), 'aa000001-0000-0000-0000-000000000001', 'CREATED',   'PENDING',   '500 ETH queued',               now() - interval '10 minutes'),
        (gen_random_uuid(), 'aa000001-0000-0000-0000-000000000001', 'SIGNED',    'SIGNED',    '500 ETH signed by MPC',        now() - interval '9 minutes 45 seconds'),
        (gen_random_uuid(), 'aa000001-0000-0000-0000-000000000001', 'BROADCAST', 'BROADCAST', '500 ETH broadcast to Sepolia', now() - interval '9 minutes 30 seconds'),
        (gen_random_uuid(), 'aa000001-0000-0000-0000-000000000001', 'SETTLED',   'SETTLED',   '500 ETH confirmed on-chain',   now() - interval '9 minutes'),

        -- 75 ETH broadcast
        (gen_random_uuid(), 'aa000002-0000-0000-0000-000000000002', 'CREATED',   'PENDING',   '75 ETH queued',                       now() - interval '8 minutes'),
        (gen_random_uuid(), 'aa000002-0000-0000-0000-000000000002', 'SIGNED',    'SIGNED',    '75 ETH signed',                       now() - interval '7 minutes 50 seconds'),
        (gen_random_uuid(), 'aa000002-0000-0000-0000-000000000002', 'BROADCAST', 'BROADCAST', '75 ETH broadcast, awaiting confirm',  now() - interval '7 minutes 40 seconds'),

        -- 1500 ETH challenge
        (gen_random_uuid(), 'aa000003-0000-0000-0000-000000000003', 'CREATED', 'PENDING_REVIEW', '1500 ETH flagged for review', now() - interval '6 minutes'),

        -- 10 ETH failed
        (gen_random_uuid(), 'aa000004-0000-0000-0000-000000000004', 'CREATED', 'PENDING', '10 ETH queued',                          now() - interval '4 minutes'),
        (gen_random_uuid(), 'aa000004-0000-0000-0000-000000000004', 'SIGNED',  'SIGNED',  '10 ETH signed',                          now() - interval '3 minutes 55 seconds'),
        (gen_random_uuid(), 'aa000004-0000-0000-0000-000000000004', 'FAILED',  'FAILED',  'Broadcast failed: insufficient funds',   now() - interval '3 minutes 50 seconds'),

        -- 1 ETH signed
        (gen_random_uuid(), 'aa000005-0000-0000-0000-000000000005', 'CREATED', 'PENDING', '1 ETH queued',          now() - interval '2 minutes'),
        (gen_random_uuid(), 'aa000005-0000-0000-0000-000000000005', 'SIGNED',  'SIGNED',  '1 ETH signed by MPC',   now() - interval '1 minute 55 seconds');
END $$;
"""


async def main() -> None:
    engine = create_async_engine(DATABASE_URL, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await session.execute(text(SEED_SQL))
        await session.commit()
    await engine.dispose()
    print("Demo DB reset complete — 10 transactions.")
    print("  1ce706e3  1 wei self-transfer     ALLOW      PENDING")
    print("  c3fde654  100 ETH cold storage    ALLOW      PENDING")
    print("  253b33ff  200 ETH partner wallet  ALLOW      PENDING")
    print("  9e703c17  9800 ETH challenge       CHALLENGE  PENDING_REVIEW")
    print("  b10c0000  50000 ETH blacklisted    BLOCK      FAILED")
    print("  aa000001  500 ETH cold storage     ALLOW      SETTLED")
    print("  aa000002  75 ETH partner wallet    ALLOW      BROADCAST")
    print("  aa000003  1500 ETH mid-size        CHALLENGE  PENDING_REVIEW")
    print("  aa000004  10 ETH cold storage      ALLOW      FAILED")
    print("  aa000005  1 ETH partner wallet     ALLOW      SIGNED")


if __name__ == "__main__":
    asyncio.run(main())
