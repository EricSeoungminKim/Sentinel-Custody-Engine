# src/orchestrator/break_glass.py
from src.orchestrator.key_sharding import reconstruct_secret


class BreakGlassRecovery:
    """Emergency recovery using any threshold-count shares including share #3."""

    def __init__(self, threshold: int) -> None:
        self.threshold = threshold

    def recover(self, active_shares: list[tuple[int, bytes]]) -> bytes:
        return reconstruct_secret(active_shares, self.threshold)
