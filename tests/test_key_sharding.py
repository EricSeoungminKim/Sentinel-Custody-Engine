import pytest
from src.orchestrator.key_sharding import split_secret, reconstruct_secret

SECRET = b"exactly-16-bytes"  # exactly 16 bytes
ETH_PRIVATE_KEY = bytes.fromhex("11" * 32)


def test_split_produces_correct_share_count():
    shares = split_secret(SECRET, threshold=2, total=3)
    assert len(shares) == 3


def test_reconstruct_with_all_shares():
    shares = split_secret(SECRET, threshold=2, total=3)
    recovered = reconstruct_secret(shares, threshold=2)
    assert recovered == SECRET


def test_reconstruct_with_minimum_shares():
    shares = split_secret(SECRET, threshold=2, total=3)
    recovered = reconstruct_secret(shares[:2], threshold=2)
    assert recovered == SECRET


def test_reconstruct_with_32_byte_private_key():
    shares = split_secret(ETH_PRIVATE_KEY, threshold=2, total=3)
    recovered = reconstruct_secret(shares[:2], threshold=2)
    assert recovered == ETH_PRIVATE_KEY


def test_reconstruct_fails_with_insufficient_shares():
    shares = split_secret(SECRET, threshold=2, total=3)
    with pytest.raises(ValueError, match="Insufficient shares"):
        reconstruct_secret(shares[:1], threshold=2)


def test_split_rejects_oversized_secret():
    with pytest.raises(ValueError, match="Secret must be <= 32 bytes"):
        split_secret(bytes.fromhex("11" * 33), threshold=2, total=3)
