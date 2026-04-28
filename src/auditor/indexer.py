# src/auditor/indexer.py
from web3 import Web3


class OnChainIndexer:
    def __init__(self, w3: Web3) -> None:
        self._w3 = w3

    def get_receipt(self, tx_hash: str) -> dict | None:
        """Fetch transaction receipt. Returns None if not yet mined."""
        try:
            receipt = self._w3.eth.get_transaction_receipt(tx_hash)
            if receipt is None:
                return None
            return {"status": receipt["status"]}
        except Exception as exc:
            raise RuntimeError(f"Receipt lookup failed for {tx_hash}: {exc}") from exc
