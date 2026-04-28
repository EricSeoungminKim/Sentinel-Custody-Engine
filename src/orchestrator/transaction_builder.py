from decimal import Decimal

from web3 import Web3

from src.models.ledger import Transaction

DEFAULT_GAS_LIMIT = 21_000
DEFAULT_MAX_PRIORITY_FEE_PER_GAS = 1_500_000_000


def eth_to_wei(amount: Decimal) -> int:
    if amount <= 0:
        raise ValueError("amount must be positive")
    return int(amount * Decimal("1000000000000000000"))


class EthereumTransactionBuilder:
    def __init__(
        self,
        w3: Web3,
        from_address: str,
        chain_id: int,
        gas_limit: int = DEFAULT_GAS_LIMIT,
        max_priority_fee_per_gas: int = DEFAULT_MAX_PRIORITY_FEE_PER_GAS,
    ) -> None:
        self._w3 = w3
        self._from_address = from_address
        self._chain_id = chain_id
        self._gas_limit = gas_limit
        self._max_priority_fee_per_gas = max_priority_fee_per_gas

    @property
    def from_address(self) -> str:
        return self._from_address

    def build(self, tx: Transaction) -> dict:
        nonce = self._w3.eth.get_transaction_count(self._from_address)
        latest_block = self._w3.eth.get_block("latest")
        base_fee = latest_block.get("baseFeePerGas", 0)
        max_fee_per_gas = base_fee + self._max_priority_fee_per_gas

        return {
            "chainId": self._chain_id,
            "nonce": nonce,
            "to": Web3.to_checksum_address(tx.to_address),
            "value": eth_to_wei(tx.amount),
            "gas": self._gas_limit,
            "maxFeePerGas": max_fee_per_gas,
            "maxPriorityFeePerGas": self._max_priority_fee_per_gas,
            "type": 2,
        }
