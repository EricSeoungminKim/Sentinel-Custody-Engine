import pytest
from eth_account import Account

from src.orchestrator.ethereum_signing import EthereumSigner

TEST_PRIVATE_KEY = bytes.fromhex(
    "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
)


def _tx_dict() -> dict:
    return {
        "chainId": 11155111,
        "nonce": 0,
        "to": "0x" + "a" * 40,
        "value": 1,
        "gas": 21_000,
        "maxFeePerGas": 20_000_000_000,
        "maxPriorityFeePerGas": 1_500_000_000,
        "type": 2,
    }


def test_ethereum_signer_rejects_non_32_byte_key():
    with pytest.raises(ValueError, match="Ethereum private key must be 32 bytes"):
        EthereumSigner(b"short")


def test_sign_transaction_returns_raw_transaction_bytes():
    signer = EthereumSigner(TEST_PRIVATE_KEY)

    raw_tx = signer.sign_transaction(_tx_dict())

    assert isinstance(raw_tx, bytes)
    assert len(raw_tx) > 0


def test_signed_transaction_recovers_expected_sender():
    signer = EthereumSigner(TEST_PRIVATE_KEY)
    raw_tx = signer.sign_transaction(_tx_dict())

    recovered = Account.recover_transaction(raw_tx)
    expected = Account.from_key(TEST_PRIVATE_KEY).address

    assert recovered == expected
