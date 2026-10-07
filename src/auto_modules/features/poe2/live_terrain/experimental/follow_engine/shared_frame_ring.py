"""Fixed-capacity shared-memory frame ring with latest-only reads."""

from __future__ import annotations

import multiprocessing as mp
from dataclasses import dataclass
from multiprocessing.shared_memory import SharedMemory
from typing import Iterator


_META_FIELDS = 6
_STATE_EMPTY = 0
_STATE_WRITING = 1
_STATE_READY = 2


@dataclass(frozen=True, slots=True)
class SharedFrameRingSpec:
    name: str
    capacity: int
    slot_size: int
    map_instance: str


@dataclass(frozen=True, slots=True)
class SharedFrameRecord:
    generation: int
    sequence: int
    captured_at_ms: int
    map_instance: str
    payload: bytes


class SharedFrameRing:
    """A bounded byte ring safe to pass to a spawned worker.

    Metadata is kept in multiprocessing primitives; the shared memory holds
    only image bytes.  Readers copy one newest slot, so processing never holds
    a slot while the producer writes a later frame.
    """

    def __init__(
        self,
        *,
        capacity: int = 3,
        slot_size: int = 4 * 1024 * 1024,
        map_instance: str = "offline",
        _spec: SharedFrameRingSpec | None = None,
        _metadata=None,
        _lock=None,
    ) -> None:
        if _spec is None:
            capacity = int(capacity)
            slot_size = int(slot_size)
            if capacity < 2 or capacity > 8 or slot_size <= 0:
                raise ValueError("frame ring capacity/slot_size is invalid")
            instance = str(map_instance).strip()
            if not instance:
                raise ValueError("map_instance is required")
            self._shm = SharedMemory(create=True, size=capacity * slot_size)
            self.spec = SharedFrameRingSpec(
                name=self._shm.name,
                capacity=capacity,
                slot_size=slot_size,
                map_instance=instance,
            )
            self._metadata = mp.Array("q", capacity * _META_FIELDS, lock=False)
            self._lock = mp.Lock()
            for index in range(capacity):
                self._set_meta(index, state=_STATE_EMPTY, sequence=-1)
        else:
            self.spec = _spec
            self._shm = SharedMemory(name=self.spec.name)
            self._metadata = _metadata
            self._lock = _lock

    def __getstate__(self):
        return {
            "spec": self.spec,
            "metadata": self._metadata,
            "lock": self._lock,
        }

    def __setstate__(self, state) -> None:
        self.__init__(_spec=state["spec"], _metadata=state["metadata"], _lock=state["lock"])

    def publish(self, record: SharedFrameRecord) -> bool:
        payload = bytes(record.payload)
        if len(payload) > self.spec.slot_size:
            raise ValueError("frame payload exceeds slot_size")
        with self._lock:
            entries = list(self._entries())
            occupied = [item for item in entries if item[0] != _STATE_EMPTY]
            if occupied and record.sequence <= max(item[1] for item in occupied):
                return False
            empty = [item for item in entries if item[0] == _STATE_EMPTY]
            if empty:
                index = empty[0][3]
            else:
                index = min(entries, key=lambda item: item[1])[3]
            self._set_meta(index, state=_STATE_WRITING, sequence=record.sequence)
            start = index * self.spec.slot_size
            self._shm.buf[start : start + len(payload)] = payload
            self._set_meta(
                index,
                state=_STATE_READY,
                generation=int(record.generation),
                sequence=int(record.sequence),
                captured_at_ms=int(record.captured_at_ms),
                payload_size=len(payload),
            )
            return True

    def read_latest(self, *, after_sequence: int = -1) -> SharedFrameRecord | None:
        with self._lock:
            ready = [item for item in self._entries() if item[0] == _STATE_READY and item[1] > int(after_sequence)]
            if not ready:
                return None
            state, sequence, captured_at_ms, index, generation, payload_size = max(ready, key=lambda item: item[1])
            start = index * self.spec.slot_size
            payload = bytes(self._shm.buf[start : start + payload_size])
            return SharedFrameRecord(generation, sequence, captured_at_ms, self.spec.map_instance, payload)

    def close(self, *, unlink: bool = False) -> None:
        name = self.spec.name
        self._shm.close()
        if unlink:
            try:
                SharedMemory(name=name).unlink()
            except FileNotFoundError:
                pass

    def _entries(self) -> Iterator[tuple[int, int, int, int, int, int]]:
        for index in range(self.spec.capacity):
            base = index * _META_FIELDS
            yield (
                int(self._metadata[base]),
                int(self._metadata[base + 1]),
                int(self._metadata[base + 2]),
                index,
                int(self._metadata[base + 3]),
                int(self._metadata[base + 4]),
            )

    def _set_meta(
        self,
        index: int,
        *,
        state: int,
        generation: int = 0,
        sequence: int = -1,
        captured_at_ms: int = 0,
        payload_size: int = 0,
    ) -> None:
        base = int(index) * _META_FIELDS
        self._metadata[base] = int(state)
        self._metadata[base + 1] = int(sequence)
        self._metadata[base + 2] = int(captured_at_ms)
        self._metadata[base + 3] = int(generation)
        self._metadata[base + 4] = int(payload_size)
        self._metadata[base + 5] = 0


__all__ = ["SharedFrameRecord", "SharedFrameRing", "SharedFrameRingSpec"]
