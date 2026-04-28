from decimal import Decimal
import uuid

import pytest
from dotenv import dotenv_values
from eth_account import Account
from web3 import Web3

from src.models.ledger import PolicyDecision, Transaction, TransactionStatus
from src.orchestrator.broadcast import BroadcastGateway
from src.orchestrator.ethereum_signing import EthereumSigner
from src.orchestrator.transaction_builder import EthereumTransactionBuilder

SEPOLIA_CHAIN_ID = 11155111


def _env_value(name: str) -> str | None:
    dotenv_value = dotenv_values(".env").get(name)
    if dotenv_value:
        return str(dotenv_value)
    return None


@pytest.fixture
def sepolia_credentials():
    rpc_url = _env_value("WEB3_RPC_URL")
    private_key = _env_value("SEPOLIA_TEST_PRIVATE_KEY")
    if not rpc_url:
        pytest.skip("WEB3_RPC_URL is not configured in .env")
    if not private_key:
        pytest.skip("SEPOLIA_TEST_PRIVATE_KEY is not configured in .env")

    private_key = private_key.removeprefix("0x")
    if len(private_key) != 64:
        pytest.skip("SEPOLIA_TEST_PRIVATE_KEY must be a 32-byte hex private key")

    w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 15}))
    chain_id = w3.eth.chain_id
    if chain_id != SEPOLIA_CHAIN_ID:
        pytest.skip(f"expected Sepolia chain id {SEPOLIA_CHAIN_ID}, got {chain_id}")

    private_key_bytes = bytes.fromhex(private_key)
    account = Account.from_key(private_key_bytes)
    return w3, private_key_bytes, account.address


@pytest.mark.sepolia_broadcast
def test_broadcasts_one_wei_self_transfer_on_sepolia(sepolia_credentials):
    w3, private_key, from_address = sepolia_credentials
    balance = w3.eth.get_balance(from_address)
    if balance <= 0:
        pytest.skip(f"test wallet has no Sepolia ETH: {from_address}")

    tx = Transaction(
        id=uuid.uuid4(),
        ledger_id=uuid.uuid4(),
        to_address=from_address,
        amount=Decimal("0.000000000000000001"),
        status=TransactionStatus.PENDING,
        policy_decision=PolicyDecision.ALLOW,
    )
    builder = EthereumTransactionBuilder(
        w3=w3,
        from_address=from_address,
        chain_id=SEPOLIA_CHAIN_ID,
    )
    signer = EthereumSigner(private_key)
    broadcaster = BroadcastGateway(w3)

    tx_dict = builder.build(tx)
    raw_tx = signer.sign_transaction(tx_dict)
    tx_hash = broadcaster.broadcast(raw_tx)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)

    print(f"Sepolia tx hash: {tx_hash}")
    print(f"Sepolia tx url: https://sepolia.etherscan.io/tx/{tx_hash}")
    assert tx_hash.startswith("0x")
    assert "0x" + receipt["transactionHash"].hex().removeprefix("0x") == tx_hash
    assert receipt["status"] == 1
