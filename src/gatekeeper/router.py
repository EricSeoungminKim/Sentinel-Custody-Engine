import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from src.auditor.audit_log import record_transaction_event
from src.models.audit import TransactionAuditLog
from src.database import get_session
from src.models.ledger import Transaction, TransactionStatus, PolicyDecision
from src.models.whitelist import WhitelistEntry
from src.gatekeeper.schemas import (
    AuditLogResponse,
    ProcessTransactionResponse,
    TransactionStatusResponse,
    WithdrawalRequest,
    WithdrawalResponse,
)
from src.gatekeeper.policy import PolicyEngine, PolicyRequest
from src.config import get_settings
from src.orchestrator.worker import process_next_pending_transaction, process_pending_transaction

router = APIRouter(prefix="/withdrawals", tags=["gatekeeper"])


async def fetch_whitelist(session: AsyncSession) -> set[str]:
    rows = await session.execute(select(WhitelistEntry.address))
    return {r for r, in rows.all()}


async def fetch_daily_spent(session: AsyncSession, ledger_id: uuid.UUID) -> Decimal:
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    result = await session.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.ledger_id == ledger_id,
            Transaction.status.notin_([TransactionStatus.FAILED, TransactionStatus.PENDING_REVIEW]),
            Transaction.created_at >= today_start,
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

    daily_limit = get_settings().daily_withdrawal_limit
    engine = PolicyEngine(whitelist_addresses=whitelist, daily_limit=daily_limit)
    decision = engine.evaluate(PolicyRequest(
        to_address=body.to_address,
        amount=body.amount,
        daily_spent=daily_spent,
    ))

    status_map = {
        PolicyDecision.ALLOW: TransactionStatus.PENDING,
        PolicyDecision.CHALLENGE: TransactionStatus.PENDING_REVIEW,
        PolicyDecision.BLOCK: TransactionStatus.FAILED,
    }
    tx = Transaction(
        ledger_id=body.ledger_id,
        to_address=body.to_address,
        amount=body.amount,
        status=status_map[decision],
        policy_decision=decision,
        id=uuid.uuid4(),
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


def _tx_response(tx: Transaction) -> TransactionStatusResponse:
    return TransactionStatusResponse(
        transaction_id=tx.id,
        ledger_id=tx.ledger_id,
        to_address=tx.to_address,
        amount=tx.amount,
        status=tx.status.value,
        policy_decision=tx.policy_decision.value if tx.policy_decision else None,
        tx_hash=tx.tx_hash,
    )


@router.post("/process-next", response_model=ProcessTransactionResponse)
async def process_next_withdrawal(
    session: AsyncSession = Depends(get_session),
) -> ProcessTransactionResponse:
    result = await process_next_pending_transaction(session)
    if result is None:
        return ProcessTransactionResponse(transaction_id=None, tx_hash=None, message="No pending transaction")
    tx_id, tx_hash = result
    return ProcessTransactionResponse(transaction_id=tx_id, tx_hash=tx_hash, message="Transaction broadcast")


@router.get("/{transaction_id}", response_model=TransactionStatusResponse)
async def get_withdrawal(
    transaction_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> TransactionStatusResponse:
    tx = await session.get(Transaction, transaction_id)
    if tx is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return _tx_response(tx)


@router.get("/{transaction_id}/audit-logs", response_model=list[AuditLogResponse])
async def get_withdrawal_audit_logs(
    transaction_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> list[AuditLogResponse]:
    rows = (
        await session.execute(
            select(TransactionAuditLog)
            .where(TransactionAuditLog.transaction_id == transaction_id)
            .order_by(TransactionAuditLog.created_at)
        )
    ).scalars().all()
    return [
        AuditLogResponse(
            transaction_id=row.transaction_id,
            event_type=row.event_type,
            status=row.status,
            tx_hash=row.tx_hash,
            message=row.message,
            created_at=row.created_at.isoformat(),
        )
        for row in rows
    ]


@router.post("/{transaction_id}/approve", response_model=TransactionStatusResponse)
async def approve_withdrawal(
    transaction_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> TransactionStatusResponse:
    tx = await session.get(Transaction, transaction_id)
    if tx is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if tx.status != TransactionStatus.PENDING_REVIEW:
        raise HTTPException(status_code=409, detail="Only PENDING_REVIEW transactions can be approved")
    tx.status = TransactionStatus.PENDING
    await record_transaction_event(session, tx.id, "APPROVED", status=tx.status, message="Manual review approved")
    await session.commit()
    await session.refresh(tx)
    return _tx_response(tx)


@router.post("/{transaction_id}/reject", response_model=TransactionStatusResponse)
async def reject_withdrawal(
    transaction_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> TransactionStatusResponse:
    tx = await session.get(Transaction, transaction_id)
    if tx is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if tx.status != TransactionStatus.PENDING_REVIEW:
        raise HTTPException(status_code=409, detail="Only PENDING_REVIEW transactions can be rejected")
    tx.status = TransactionStatus.FAILED
    await record_transaction_event(session, tx.id, "REJECTED", status=tx.status, message="Manual review rejected")
    await session.commit()
    await session.refresh(tx)
    return _tx_response(tx)


@router.post("/{transaction_id}/process", response_model=ProcessTransactionResponse)
async def process_withdrawal(
    transaction_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> ProcessTransactionResponse:
    tx_hash = await process_pending_transaction(session, transaction_id)
    if tx_hash is None:
        raise HTTPException(status_code=409, detail="Transaction is not processable")
    return ProcessTransactionResponse(transaction_id=transaction_id, tx_hash=tx_hash, message="Transaction broadcast")
