import asyncio
from decimal import Decimal
import os
from pathlib import Path
import uuid

from dotenv import dotenv_values
from eth_account import Account
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from web3 import Web3

from src.auditor.indexer import OnChainIndexer
from src.auditor.reconciler import Reconciler
from src.models.ledger import Ledger, PolicyDecision, Transaction, TransactionStatus
from src.orchestrator.broadcast import BroadcastGateway
from src.orchestrator.ethereum_signing import EthereumSigner
from src.orchestrator.lifecycle import EthereumTransactionLifecycleProcessor
from src.orchestrator.transaction_builder import EthereumTransactionBuilder

SEPOLIA_CHAIN_ID = 11155111
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DOTENV = dotenv_values(_PROJECT_ROOT / ".env")


def _required_env(name: str) -> str:
    value = os.getenv(name) or _DOTENV.get(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


async def run_record_demo() -> None:
    database_url = _required_env("DATABASE_URL")
    web3_rpc_url = _required_env("WEB3_RPC_URL")
    private_key_hex = _required_env("SEPOLIA_TEST_PRIVATE_KEY").removeprefix("0x")
    private_key = bytes.fromhex(private_key_hex)
    from_address = Account.from_key(private_key).address

    w3 = Web3(Web3.HTTPProvider(web3_rpc_url, request_kwargs={"timeout": 15}))
    chain_id = w3.eth.chain_id
    if chain_id != SEPOLIA_CHAIN_ID:
        raise RuntimeError(f"Expected Sepolia chain id {SEPOLIA_CHAIN_ID}, got {chain_id}")
    if w3.eth.get_balance(from_address) <= 0:
        raise RuntimeError(f"Test wallet has no Sepolia ETH: {from_address}")

    engine = create_async_engine(database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    ledger_id = uuid.uuid4()
    tx_id = uuid.uuid4()
    async with session_factory() as session:
        ledger = Ledger(
            id=ledger_id,
            name="record-demo-ledger",
            balance=Decimal("100000"),
        )
        tx = Transaction(
            id=tx_id,
            ledger_id=ledger_id,
            to_address=from_address,
            amount=Decimal("0.000000000000000001"),
            status=TransactionStatus.PENDING,
            policy_decision=PolicyDecision.ALLOW,
        )
        session.add_all([ledger, tx])
        await session.commit()

        processor = EthereumTransactionLifecycleProcessor(
            session=session,
            transaction_builder=EthereumTransactionBuilder(
                w3=w3,
                from_address=from_address,
                chain_id=SEPOLIA_CHAIN_ID,
            ),
            signer=EthereumSigner(private_key),
            broadcaster=BroadcastGateway(w3),
        )
        tx_hash = await processor.process_pending(tx_id)
        w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)

        reconciler = Reconciler(session=session, indexer=OnChainIndexer(w3))
        await reconciler.sync(tx_id)

        settled_tx = await session.get(Transaction, tx_id)
        print(f"record_demo transaction_id: {tx_id}")
        print(f"record_demo ledger_id: {ledger_id}")
        print(f"record_demo status: {settled_tx.status.value if settled_tx else 'missing'}")
        print(f"record_demo tx hash: {tx_hash}")
        print(f"record_demo tx url: https://sepolia.etherscan.io/tx/{tx_hash}")

    await engine.dispose()


def main() -> None:
    asyncio.run(run_record_demo())


if __name__ == "__main__":
    main()
