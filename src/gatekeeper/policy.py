from dataclasses import dataclass
from decimal import Decimal
from src.models.ledger import PolicyDecision


@dataclass(frozen=True)
class PolicyRequest:
    to_address: str
    amount: Decimal
    daily_spent: Decimal


class PolicyEngine:
    def __init__(self, whitelist_addresses: set[str], daily_limit: Decimal) -> None:
        self._whitelist = whitelist_addresses
        self._daily_limit = daily_limit

    def evaluate(self, request: PolicyRequest) -> PolicyDecision:
        if request.amount <= 0:
            return PolicyDecision.BLOCK
        if request.to_address not in self._whitelist:
            return PolicyDecision.BLOCK
        if request.daily_spent + request.amount > self._daily_limit:
            return PolicyDecision.CHALLENGE
        return PolicyDecision.ALLOW
