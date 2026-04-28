from eth_account import Account
from web3 import Web3


class EthereumSigner:
    def __init__(self, private_key: bytes) -> None:
        if len(private_key) != 32:
            raise ValueError("Ethereum private key must be 32 bytes")
        self._private_key = private_key

    def sign_transaction(self, tx_dict: dict) -> bytes:
        normalized = dict(tx_dict)
        if normalized.get("to"):
            normalized["to"] = Web3.to_checksum_address(normalized["to"])
        signed = Account.sign_transaction(normalized, private_key=self._private_key)
        return bytes(signed.raw_transaction)
