"""
Web3 broadcast gateway for sending signed transactions to the blockchain network.
Handles error propagation and hex conversion of transaction hashes.
"""
from web3 import Web3


class BroadcastGateway:
    """Gateway for broadcasting signed transactions to Ethereum network.

    Wraps Web3 transaction submission with error handling and type conversion.
    """

    def __init__(self, w3: Web3) -> None:
        """Initialize gateway with Web3 instance.

        Args:
            w3: Web3 instance configured with network provider
        """
        self._w3 = w3

    def broadcast(self, signed_tx: bytes) -> str:
        """Send raw signed transaction to network.

        Submits a raw transaction bytes to the connected blockchain network
        and returns the transaction hash as a hex string.

        Args:
            signed_tx: Raw signed transaction bytes

        Returns:
            Transaction hash as hex string (e.g., "0xabcd...")

        Raises:
            RuntimeError: If transaction submission fails
        """
        try:
            raw_hash = self._w3.eth.send_raw_transaction(signed_tx)
            return self._w3.to_hex(raw_hash)
        except Exception as exc:
            raise RuntimeError(f"Broadcast failed: {exc}") from exc
