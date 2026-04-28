from decimal import Decimal
import uuid

import pytest
from dotenv import dotenv_values
from web3 import Web3

from src.config import Settings
from src.models.ledger import PolicyDecision, Transaction, TransactionStatus
from src.orchestrator.transaction_builder import EthereumTransactionBuilder

SEPOLIA_CHAIN_ID = 11155111


def _web3_rpc_url() -> str:
    dotenv_web3_rpc_url = dotenv_values(".env").get("WEB3_RPC_URL")
    if dotenv_web3_rpc_url:
        return str(dotenv_web3_rpc_url)
    return Settings().web3_rpc_url


@pytest.fixture
def sepolia_w3():
    try:
        web3_rpc_url = _web3_rpc_url()
    except Exception as exc:
        pytest.skip(f"settings unavailable: {exc}")

    w3 = Web3(Web3.HTTPProvider(web3_rpc_url, request_kwargs={"timeout": 10}))
    try:
        chain_id = w3.eth.chain_id
    except Exception as exc:
        pytest.skip(f"web3 rpc unavailable: {exc}")

    if chain_id != SEPOLIA_CHAIN_ID:
        pytest.skip(f"expected Sepolia chain id {SEPOLIA_CHAIN_ID}, got {chain_id}")
    return w3


def test_sepolia_rpc_returns_latest_block(sepolia_w3):
    latest_block = sepolia_w3.eth.get_block("latest")

    assert latest_block["number"] > 0
    assert "hash" in latest_block


def test_transaction_builder_reads_nonce_and_base_fee_from_sepolia(sepolia_w3):
    from_address = "0x" + "1" * 40
    tx = Transaction(
        id=uuid.uuid4(),
        ledger_id=uuid.uuid4(),
        to_address="0x" + "a" * 40,
        amount=Decimal("0.000001"),
        status=TransactionStatus.PENDING,
        policy_decision=PolicyDecision.ALLOW,
    )
    builder = EthereumTransactionBuilder(
        w3=sepolia_w3,
        from_address=from_address,
        chain_id=SEPOLIA_CHAIN_ID,
    )

    tx_dict = builder.build(tx)

    assert tx_dict["chainId"] == SEPOLIA_CHAIN_ID
    assert tx_dict["nonce"] >= 0
    assert tx_dict["value"] == 1_000_000_000_000
    assert tx_dict["maxFeePerGas"] >= tx_dict["maxPriorityFeePerGas"]
