import pytest
from decimal import Decimal
from src.gatekeeper.policy import PolicyEngine, PolicyRequest, PolicyDecision

WHITELIST = {"0xAPPROVED"}

@pytest.fixture
def engine():
    return PolicyEngine(whitelist_addresses=WHITELIST, daily_limit=Decimal("100"))

def test_allow_whitelisted_address_under_limit(engine):
    req = PolicyRequest(to_address="0xAPPROVED", amount=Decimal("50"), daily_spent=Decimal("0"))
    result = engine.evaluate(req)
    assert result == PolicyDecision.ALLOW

def test_block_non_whitelisted_address(engine):
    req = PolicyRequest(to_address="0xBLACKLIST", amount=Decimal("1"), daily_spent=Decimal("0"))
    result = engine.evaluate(req)
    assert result == PolicyDecision.BLOCK

def test_challenge_when_daily_limit_exceeded(engine):
    req = PolicyRequest(to_address="0xAPPROVED", amount=Decimal("60"), daily_spent=Decimal("50"))
    result = engine.evaluate(req)
    assert result == PolicyDecision.CHALLENGE

def test_block_zero_amount(engine):
    req = PolicyRequest(to_address="0xAPPROVED", amount=Decimal("0"), daily_spent=Decimal("0"))
    result = engine.evaluate(req)
    assert result == PolicyDecision.BLOCK
