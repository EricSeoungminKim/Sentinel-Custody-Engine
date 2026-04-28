import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.auditor.audit_log import record_transaction_event
from src.models.ledger import Transaction, TransactionStatus
from src.orchestrator.broadcast import BroadcastGateway
from src.orchestrator.ethereum_signing import EthereumSigner
from src.orchestrator.nonce import nonce_lock
from src.orchestrator.signing import MPCSigner
from src.orchestrator.transaction_builder import EthereumTransactionBuilder


def serialize_transaction_for_signing(tx: Transaction) -> bytes:
    payload = "|".join([
        str(tx.id),
        str(tx.ledger_id),
        tx.to_address,
        str(tx.amount),
    ])
    return payload.encode()


class TransactionLifecycleProcessor:
    def __init__(
        self,
        session: AsyncSession,
        signer: MPCSigner,
        broadcaster: BroadcastGateway,
        active_shares: list[tuple[int, bytes]],
    ) -> None:
        self.session = session
        self.signer = signer
        self.broadcaster = broadcaster
        self.active_shares = active_shares

    async def sign_pending(self, tx_id: uuid.UUID) -> bytes | None:
        tx = await self.session.get(Transaction, tx_id)
        if tx is None or tx.status != TransactionStatus.PENDING:
            return None

        signed_payload = self.signer.sign(
            serialize_transaction_for_signing(tx),
            active_shares=self.active_shares,
        )
        tx.status = TransactionStatus.SIGNED
        await record_transaction_event(
            self.session,
            tx.id,
            "SIGNED",
            status=tx.status,
            message="Transaction signed by simulation MPC signer",
        )
        await self.session.commit()
        return signed_payload

    async def broadcast_signed(self, tx_id: uuid.UUID, signed_payload: bytes) -> str | None:
        tx = await self.session.get(Transaction, tx_id)
        if tx is None or tx.status != TransactionStatus.SIGNED:
            return None

        tx_hash = self.broadcaster.broadcast(signed_payload)
        tx.tx_hash = tx_hash
        tx.status = TransactionStatus.BROADCAST
        await record_transaction_event(
            self.session,
            tx.id,
            "BROADCAST",
            status=tx.status,
            tx_hash=tx_hash,
            message="Transaction broadcast by simulation lifecycle",
        )
        await self.session.commit()
        return tx_hash

    async def process_pending(self, tx_id: uuid.UUID) -> str | None:
        signed_payload = await self.sign_pending(tx_id)
        if signed_payload is None:
            return None
        return await self.broadcast_signed(tx_id, signed_payload)


class EthereumTransactionLifecycleProcessor:
    def __init__(
        self,
        session: AsyncSession,
        transaction_builder: EthereumTransactionBuilder,
        signer: EthereumSigner,
        broadcaster: BroadcastGateway,
    ) -> None:
        self.session = session
        self.transaction_builder = transaction_builder
        self.signer = signer
        self.broadcaster = broadcaster

    async def process_pending(self, tx_id: uuid.UUID) -> str | None:
        tx = await self.session.get(Transaction, tx_id)
        if tx is None or tx.status != TransactionStatus.PENDING:
            return None

        async with nonce_lock(self.transaction_builder.from_address):
            tx_dict = self.transaction_builder.build(tx)
            signed_payload = self.signer.sign_transaction(tx_dict)
            tx.status = TransactionStatus.SIGNED
            await record_transaction_event(
                self.session,
                tx.id,
                "SIGNED",
                status=tx.status,
                message="Ethereum transaction signed",
            )
            await self.session.commit()

            tx_hash = self.broadcaster.broadcast(signed_payload)
            tx.tx_hash = tx_hash
            tx.status = TransactionStatus.BROADCAST
            await record_transaction_event(
                self.session,
                tx.id,
                "BROADCAST",
                status=tx.status,
                tx_hash=tx_hash,
                message="Ethereum transaction broadcast",
            )
            await self.session.commit()
            return tx_hash
