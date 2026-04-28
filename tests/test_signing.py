import pytest
from src.orchestrator.key_sharding import split_secret
from src.orchestrator.signing import MPCSigner

SECRET = bytes.fromhex("22" * 32)


def _make_shares(secret: bytes):
    return split_secret(secret, threshold=2, total=3)


@pytest.fixture
def signer():
    shares = _make_shares(SECRET)
    return MPCSigner(all_shares=shares, threshold=2)


def test_sign_with_two_shares(signer):
    active_shares = signer.all_shares[:2]
    result = signer.sign(tx_data=b"tx-payload", active_shares=active_shares)
    assert result is not None
    assert isinstance(result, bytes)


def test_sign_with_all_shares(signer):
    result = signer.sign(tx_data=b"tx-payload", active_shares=signer.all_shares)
    assert result is not None


def test_sign_fails_with_one_share(signer):
    with pytest.raises(ValueError, match="Insufficient shares"):
        signer.sign(tx_data=b"tx-payload", active_shares=signer.all_shares[:1])


def test_mpc_test_from_plan():
    """Reproduces plan.md 4.2: 1 node offline, 2 shares still sign."""
    shares = split_secret(SECRET, threshold=2, total=3)
    share_1, share_2, _share_3 = shares  # share_3 offline
    signer = MPCSigner(all_shares=shares, threshold=2)
    signature = signer.sign(b"tx-data", active_shares=[share_1, share_2])
    assert signature is not None
