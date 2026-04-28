# src/auditor/reconciler.py
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.auditor.audit_log import record_transaction_event
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
        if tx.status != TransactionStatus.BROADCAST:
            return  # only reconcile transactions that are broadcast

        receipt = self.indexer.get_receipt(tx.tx_hash)
        if receipt is None:
            return

        if receipt["status"] == 1:
            tx.status = TransactionStatus.SETTLED
            tx.settled_at = datetime.now(timezone.utc)
            await record_transaction_event(
                self.session,
                tx.id,
                "SETTLED",
                status=tx.status,
                tx_hash=tx.tx_hash,
                message="On-chain receipt status 1",
            )
        else:
            tx.status = TransactionStatus.FAILED
            await record_transaction_event(
                self.session,
                tx.id,
                "FAILED",
                status=tx.status,
                tx_hash=tx.tx_hash,
                message="On-chain receipt status 0",
            )

        await self.session.commit()
