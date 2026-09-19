"""In-memory ownership for the current PoE2 terrain snapshot."""

from __future__ import annotations

from .contracts import TerrainSnapshot


class MemoryTerrainStore:
    def __init__(self) -> None:
        self._snapshot: TerrainSnapshot | None = None

    def snapshot(self) -> TerrainSnapshot | None:
        return self._snapshot

    def replace(self, snapshot: TerrainSnapshot) -> TerrainSnapshot:
        self._snapshot = snapshot
        return snapshot

    def clear(self) -> None:
        self._snapshot = None
