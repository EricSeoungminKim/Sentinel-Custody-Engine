import pytest
from unittest.mock import MagicMock
from src.orchestrator.broadcast import BroadcastGateway


def test_broadcast_returns_tx_hash():
    mock_w3 = MagicMock()
    mock_w3.eth.send_raw_transaction.return_value = bytes.fromhex("deadbeef" * 8)
    mock_w3.to_hex.return_value = "0x" + "deadbeef" * 8

    gw = BroadcastGateway(w3=mock_w3)
    tx_hash = gw.broadcast(signed_tx=b"signed-tx-bytes")

    mock_w3.eth.send_raw_transaction.assert_called_once_with(b"signed-tx-bytes")
    assert tx_hash.startswith("0x")


def test_broadcast_propagates_web3_error():
    mock_w3 = MagicMock()
    mock_w3.eth.send_raw_transaction.side_effect = Exception("network error")

    gw = BroadcastGateway(w3=mock_w3)
    with pytest.raises(RuntimeError, match="Broadcast failed"):
        gw.broadcast(signed_tx=b"signed-tx-bytes")
