"""One-shot authorization for expensive absolute-recovery attempts."""

from __future__ import annotations


class OneShotRecoveryPolicy:
    def __init__(self) -> None:
        self._revision = 0
        self._consumed: set[int] = set()

    @property
    def revision(self) -> int:
        return self._revision

    def begin(self) -> int:
        self._revision += 1
        return self._revision

    def consume(self, revision: int) -> bool:
        revision = int(revision)
        if revision != self._revision or revision in self._consumed:
            return False
        self._consumed.add(revision)
        return True


__all__ = ["OneShotRecoveryPolicy"]
