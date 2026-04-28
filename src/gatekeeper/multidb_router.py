"""Read-only endpoint that queries all three databases and returns combined results."""
import asyncio

from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from src.config import get_settings

router = APIRouter(tags=["multidb"])

_TRANSACTIONS_SQL = text("""
    SELECT
        id::text,
        ledger_id::text,
        to_address,
        amount::text,
        status,
        policy_decision,
        tx_hash,
        settled_at AT TIME ZONE 'America/Los_Angeles' AS settled_at_la,
        created_at AT TIME ZONE 'America/Los_Angeles' AS created_at_la
    FROM transactions
    ORDER BY created_at DESC
""")

_AUDIT_SQL = text("""
    SELECT
        transaction_id::text,
        event_type,
        status,
        tx_hash,
        message,
        created_at AT TIME ZONE 'America/Los_Angeles' AS created_at_la
    FROM transaction_audit_logs
    ORDER BY created_at DESC
""")


def _fmt(dt) -> str | None:
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%d %H:%M:%S")


async def _query_db(url: str, db_label: str) -> dict:
    engine = create_async_engine(url, pool_pre_ping=True, connect_args={"timeout": 5})
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            tx_rows = (await session.execute(_TRANSACTIONS_SQL)).mappings().all()
            audit_rows = (await session.execute(_AUDIT_SQL)).mappings().all()
        return {
            "db": db_label,
            "ok": True,
            "transactions": [
                {
                    "id": r["id"],
                    "ledger_id": r["ledger_id"],
                    "to_address": r["to_address"],
                    "amount": r["amount"],
                    "status": r["status"],
                    "policy_decision": r["policy_decision"],
                    "tx_hash": r["tx_hash"],
                    "settled_at": _fmt(r["settled_at_la"]),
                    "created_at": _fmt(r["created_at_la"]),
                }
                for r in tx_rows
            ],
            "audit_logs": [
                {
                    "transaction_id": r["transaction_id"],
                    "event_type": r["event_type"],
                    "status": r["status"],
                    "tx_hash": r["tx_hash"],
                    "message": r["message"],
                    "created_at": _fmt(r["created_at_la"]),
                }
                for r in audit_rows
            ],
        }
    except Exception as exc:
        return {"db": db_label, "ok": False, "error": str(exc), "transactions": [], "audit_logs": []}
    finally:
        await engine.dispose()


@router.get("/multi-db", include_in_schema=True)
async def multi_db_snapshot() -> list[dict]:
    """Return transactions + audit logs from all three databases."""
    settings = get_settings()
    results = await asyncio.gather(
        _query_db(settings.database_url, "dev"),
        _query_db(settings.database_url_test, "test"),
        _query_db(settings.database_url_record, "record"),
    )
    return list(results)
