from src.models.ledger import Ledger, Transaction, TransactionStatus
from src.models.whitelist import WhitelistEntry


def test_transaction_status_values():
    assert TransactionStatus.PENDING == "PENDING"
    assert TransactionStatus.SETTLED == "SETTLED"
    assert TransactionStatus.FAILED == "FAILED"


def test_whitelist_entry_has_address():
    entry = WhitelistEntry(address="0xABC", label="treasury")
    assert entry.address == "0xABC"
