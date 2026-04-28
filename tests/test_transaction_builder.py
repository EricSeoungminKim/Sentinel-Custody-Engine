import uuid
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from web3 import Web3

from src.models.ledger import PolicyDecision, Transaction, TransactionStatus
from src.orchestrator.transaction_builder import (
    DEFAULT_GAS_LIMIT,
    DEFAULT_MAX_PRIORITY_FEE_PER_GAS,
    EthereumTransactionBuilder,
    eth_to_wei,
)


def _transaction(amount: Decimal = Decimal("1.5")) -> Transaction:
    return Transaction(
        id=uuid.uuid4(),
        ledger_id=uuid.uuid4(),
        to_address="0x" + "a" * 40,
        amount=amount,
        status=TransactionStatus.SIGNED,
        policy_decision=PolicyDecision.ALLOW,
    )


def test_eth_to_wei_converts_decimal_eth_amount():
    assert eth_to_wei(Decimal("1")) == 1_000_000_000_000_000_000
    assert eth_to_wei(Decimal("0.000000000000000001")) == 1


def test_eth_to_wei_rejects_non_positive_amount():
    with pytest.raises(ValueError, match="amount must be positive"):
        eth_to_wei(Decimal("0"))


def test_builds_eip1559_transaction_dict():
    mock_w3 = MagicMock()
    mock_w3.eth.get_transaction_count.return_value = 7
    mock_w3.eth.get_block.return_value = {"baseFeePerGas": 20_000_000_000}
    from_address = "0x" + "f" * 40
    builder = EthereumTransactionBuilder(
        w3=mock_w3,
        from_address=from_address,
        chain_id=11155111,
    )

    built = builder.build(_transaction())

    assert built == {
        "chainId": 11155111,
        "nonce": 7,
        "to": Web3.to_checksum_address("0x" + "a" * 40),
        "value": 1_500_000_000_000_000_000,
        "gas": DEFAULT_GAS_LIMIT,
        "maxFeePerGas": 20_000_000_000 + DEFAULT_MAX_PRIORITY_FEE_PER_GAS,
        "maxPriorityFeePerGas": DEFAULT_MAX_PRIORITY_FEE_PER_GAS,
        "type": 2,
    }
    mock_w3.eth.get_transaction_count.assert_called_once_with(from_address)
    mock_w3.eth.get_block.assert_called_once_with("latest")
