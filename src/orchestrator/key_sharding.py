"""
Shamir's Secret Sharing wrapper using PyCryptodome.
Each share is a (index, bytes) tuple for transport/storage.
PyCryptodome Shamir requires exactly 16-byte blocks, so 32-byte keys are split
into two blocks and packed back into a single share payload.
"""
from Crypto.Protocol.SecretSharing import Shamir

BLOCK_SIZE = 16
MAX_SECRET_SIZE = 32
LENGTH_PREFIX_SIZE = 1


def split_secret(secret: bytes, threshold: int, total: int) -> list[tuple[int, bytes]]:
    """Split secret into `total` shares; any `threshold` can reconstruct.
    Secret must be <= 32 bytes, which covers Ethereum private keys.
    """
    if len(secret) > MAX_SECRET_SIZE:
        raise ValueError(f"Secret must be <= {MAX_SECRET_SIZE} bytes for Shamir SSS; got {len(secret)}")

    normalized = secret.ljust(MAX_SECRET_SIZE, b"\x00")
    chunks = [
        normalized[offset:offset + BLOCK_SIZE]
        for offset in range(0, MAX_SECRET_SIZE, BLOCK_SIZE)
    ]
    chunked_shares = [Shamir.split(threshold, total, chunk) for chunk in chunks]

    shares: list[tuple[int, bytes]] = []
    for share_index in range(total):
        index = chunked_shares[0][share_index][0]
        payload = bytes([len(secret)])
        payload += b"".join(chunk_shares[share_index][1] for chunk_shares in chunked_shares)
        shares.append((index, payload))
    return shares


def reconstruct_secret(shares: list[tuple[int, bytes]], threshold: int) -> bytes:
    """Reconstruct secret from at least `threshold` shares."""
    if len(shares) < threshold:
        raise ValueError(f"Insufficient shares: need {threshold}, got {len(shares)}")

    secret_len = shares[0][1][0]
    if secret_len > MAX_SECRET_SIZE:
        raise ValueError(f"Invalid share payload length: {secret_len}")

    reconstructed = bytearray()
    for offset in range(LENGTH_PREFIX_SIZE, LENGTH_PREFIX_SIZE + MAX_SECRET_SIZE, BLOCK_SIZE):
        chunk_shares = [(index, payload[offset:offset + BLOCK_SIZE]) for index, payload in shares]
        reconstructed.extend(Shamir.combine(chunk_shares))
    return bytes(reconstructed[:secret_len])
