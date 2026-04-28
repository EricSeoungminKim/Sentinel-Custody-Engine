import pytest
from src.orchestrator.key_sharding import split_secret
from src.orchestrator.break_glass import BreakGlassRecovery

SECRET = b"emergency-privat"  # exactly 16 bytes


def test_break_glass_recovery_with_emergency_share():
    shares = split_secret(SECRET, threshold=2, total=3)
    share_1, _share_2, share_3 = shares  # share_2 unavailable

    recovery = BreakGlassRecovery(threshold=2)
    recovered = recovery.recover(active_shares=[share_1, share_3])
    assert isinstance(recovered, bytes)
    assert len(recovered) == 16


def test_break_glass_fails_without_enough_shares():
    shares = split_secret(SECRET, threshold=2, total=3)
    recovery = BreakGlassRecovery(threshold=2)
    with pytest.raises(ValueError, match="Insufficient shares"):
        recovery.recover(active_shares=[shares[0]])
