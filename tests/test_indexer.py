import pytest
from unittest.mock import MagicMock
from web3.exceptions import TransactionNotFound

from src.auditor.indexer import OnChainIndexer


def test_get_receipt_returns_none_when_pending():
    mock_w3 = MagicMock()
    mock_w3.eth.get_transaction_receipt.return_value = None

    indexer = OnChainIndexer(mock_w3)

    assert indexer.get_receipt("0xpending") is None


def test_get_receipt_returns_none_on_transaction_not_found():
    mock_w3 = MagicMock()
    mock_w3.eth.get_transaction_receipt.side_effect = TransactionNotFound("tx not found")

    indexer = OnChainIndexer(mock_w3)

    assert indexer.get_receipt("0xunknown") is None


def test_get_receipt_raises_on_rpc_error():
    mock_w3 = MagicMock()
    mock_w3.eth.get_transaction_receipt.side_effect = Exception("rpc down")

    indexer = OnChainIndexer(mock_w3)

    with pytest.raises(RuntimeError, match="Receipt lookup failed"):
        indexer.get_receipt("0xerror")
