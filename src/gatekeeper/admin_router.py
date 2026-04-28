import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from web3 import Web3

from src.auditor.indexer import OnChainIndexer
from src.auditor.reconciler import Reconciler
from src.config import get_settings
from src.database import get_session
from src.gatekeeper.router import _tx_response
from src.gatekeeper.schemas import (
    LedgerResponse,
    ReconcileTransactionResponse,
    StatsResponse,
    TransactionStatusResponse,
    WhitelistEntryRequest,
    WhitelistEntryResponse,
)
from src.models.ledger import Ledger, PolicyDecision, Transaction, TransactionStatus
from src.models.whitelist import WhitelistEntry

router = APIRouter(tags=["admin"])


def _ledger_response(ledger: Ledger) -> LedgerResponse:
    return LedgerResponse(
        id=ledger.id,
        name=ledger.name,
        balance=ledger.balance,
        created_at=ledger.created_at.isoformat(),
    )


def _whitelist_response(entry: WhitelistEntry) -> WhitelistEntryResponse:
    return WhitelistEntryResponse(
        id=entry.id,
        address=entry.address,
        label=entry.label,
        created_at=entry.created_at.isoformat(),
    )


@router.get("/withdrawals", response_model=list[TransactionStatusResponse])
async def list_withdrawals(
    status: TransactionStatus | None = None,
    ledger_id: uuid.UUID | None = None,
    limit: int = 100,
    session: AsyncSession = Depends(get_session),
) -> list[TransactionStatusResponse]:
    stmt = select(Transaction).order_by(Transaction.created_at.desc()).limit(min(limit, 500))
    if status is not None:
        stmt = stmt.where(Transaction.status == status)
    if ledger_id is not None:
        stmt = stmt.where(Transaction.ledger_id == ledger_id)
    rows = (await session.execute(stmt)).scalars().all()
    return [_tx_response(tx) for tx in rows]


@router.get("/ledgers", response_model=list[LedgerResponse])
async def list_ledgers(session: AsyncSession = Depends(get_session)) -> list[LedgerResponse]:
    rows = (await session.execute(select(Ledger).order_by(Ledger.created_at.desc()))).scalars().all()
    return [_ledger_response(ledger) for ledger in rows]


@router.get("/ledgers/{ledger_id}/transactions", response_model=list[TransactionStatusResponse])
async def list_ledger_transactions(
    ledger_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> list[TransactionStatusResponse]:
    ledger = await session.get(Ledger, ledger_id)
    if ledger is None:
        raise HTTPException(status_code=404, detail="Ledger not found")
    rows = (
        await session.execute(
            select(Transaction)
            .where(Transaction.ledger_id == ledger_id)
            .order_by(Transaction.created_at.desc())
        )
    ).scalars().all()
    return [_tx_response(tx) for tx in rows]


@router.get("/whitelist", response_model=list[WhitelistEntryResponse])
async def list_whitelist(session: AsyncSession = Depends(get_session)) -> list[WhitelistEntryResponse]:
    rows = (await session.execute(select(WhitelistEntry).order_by(WhitelistEntry.created_at.desc()))).scalars().all()
    return [_whitelist_response(entry) for entry in rows]


@router.post("/whitelist", response_model=WhitelistEntryResponse)
async def add_whitelist_entry(
    body: WhitelistEntryRequest,
    session: AsyncSession = Depends(get_session),
) -> WhitelistEntryResponse:
    entry = WhitelistEntry(address=body.address, label=body.label)
    session.add(entry)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Whitelist address already exists") from exc
    await session.refresh(entry)
    return _whitelist_response(entry)


@router.delete("/whitelist/{address}", status_code=204)
async def delete_whitelist_entry(
    address: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    result = await session.execute(delete(WhitelistEntry).where(WhitelistEntry.address == address))
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Whitelist address not found")
    await session.commit()


@router.post("/transactions/{transaction_id}/reconcile", response_model=ReconcileTransactionResponse)
async def reconcile_transaction(
    transaction_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> ReconcileTransactionResponse:
    tx = await session.get(Transaction, transaction_id)
    if tx is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    before = tx.status
    w3 = Web3(Web3.HTTPProvider(get_settings().web3_rpc_url, request_kwargs={"timeout": 15}))
    await Reconciler(session=session, indexer=OnChainIndexer(w3)).sync(transaction_id)
    await session.refresh(tx)
    return ReconcileTransactionResponse(
        transaction_id=tx.id,
        status=tx.status.value,
        message=f"Reconciled from {before.value} to {tx.status.value}",
    )


@router.get("/stats", response_model=StatsResponse)
async def get_stats(session: AsyncSession = Depends(get_session)) -> StatsResponse:
    total_transactions = await session.scalar(select(func.count()).select_from(Transaction)) or 0
    total_ledgers = await session.scalar(select(func.count()).select_from(Ledger)) or 0
    total_whitelist_entries = await session.scalar(select(func.count()).select_from(WhitelistEntry)) or 0

    status_counts = {status.value: 0 for status in TransactionStatus}
    status_rows = await session.execute(select(Transaction.status, func.count()).group_by(Transaction.status))
    for status, count in status_rows.all():
        status_counts[status.value] = count

    decision_counts = {decision.value: 0 for decision in PolicyDecision}
    decision_rows = await session.execute(select(Transaction.policy_decision, func.count()).group_by(Transaction.policy_decision))
    for decision, count in decision_rows.all():
        if decision is not None:
            decision_counts[decision.value] = count

    return StatsResponse(
        total_transactions=total_transactions,
        by_status=status_counts,
        by_policy_decision=decision_counts,
        total_ledgers=total_ledgers,
        total_whitelist_entries=total_whitelist_entries,
    )
