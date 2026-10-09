"""Fixed-capacity shared-memory frame ring with latest-only reads."""

from __future__ import annotations

import multiprocessing as mp
from contextlib import contextmanager
from dataclasses import dataclass, replace
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


def _normalize_header(generation: int, sequence: int, captured_at_ms: int, map_instance: str) -> tuple[int, int, int, str]:
    generation = int(generation)
    sequence = int(sequence)
    captured_at_ms = int(captured_at_ms)
    map_instance = str(map_instance).strip()
    if generation <= 0 or sequence < 0 or captured_at_ms < 0 or not map_instance:
        raise ValueError("frame header is invalid")
    return generation, sequence, captured_at_ms, map_instance


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
        _broken=None,
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
            self._broken = mp.Value("b", False, lock=False)
            self._unlinked = False
            for index in range(capacity):
                self._set_meta(index, state=_STATE_EMPTY, sequence=-1)
        else:
            self.spec = _spec
            self._shm = SharedMemory(name=self.spec.name)
            self._metadata = _metadata
            self._lock = _lock
            self._broken = _broken
            self._unlinked = False

    def __getstate__(self):
        return {
            "spec": self.spec,
            "metadata": self._metadata,
            "lock": self._lock,
            "broken": self._broken,
        }

    def __setstate__(self, state) -> None:
        self.__init__(_spec=state["spec"], _metadata=state["metadata"], _lock=state["lock"], _broken=state["broken"])

    def invalidate(self) -> None:
        """Poison this allocation; only replacing the entire ring can recover it."""
        self._broken.value = True

    @contextmanager
    def _locked(self):
        if self._broken.value or not self._lock.acquire(timeout=0.05):
            self.invalidate()
            raise TimeoutError("shared frame ring lock unavailable; replace allocation")
        try:
            if self._broken.value:
                raise TimeoutError("shared frame ring allocation is invalid")
            yield
        finally:
            self._lock.release()

    def publish(self, record: SharedFrameRecord) -> bool:
        generation, sequence, captured_at_ms, map_instance = _normalize_header(
            record.generation, record.sequence, record.captured_at_ms, record.map_instance
        )
        if map_instance != self.spec.map_instance:
            raise ValueError("frame belongs to a different map instance")
        payload = bytes(record.payload)
        if len(payload) > self.spec.slot_size:
            raise ValueError("frame payload exceeds slot_size")
        with self._locked():
            entries = list(self._entries())
            occupied = [item for item in entries if item[0] != _STATE_EMPTY]
            if occupied and sequence <= max(item[1] for item in occupied):
                return False
            empty = [item for item in entries if item[0] == _STATE_EMPTY]
            if empty:
                index = empty[0][3]
            else:
                index = min(entries, key=lambda item: item[1])[3]
            self._set_meta(index, state=_STATE_WRITING, sequence=sequence)
            start = index * self.spec.slot_size
            self._shm.buf[start : start + len(payload)] = payload
            self._set_meta(
                index,
                state=_STATE_READY,
                generation=generation,
                sequence=sequence,
                captured_at_ms=captured_at_ms,
                payload_size=len(payload),
            )
            return True

    def read_latest(self, *, after_sequence: int = -1) -> SharedFrameRecord | None:
        with self._locked():
            ready = [item for item in self._entries() if item[0] == _STATE_READY and item[1] > int(after_sequence)]
            if not ready:
                return None
            state, sequence, captured_at_ms, index, generation, payload_size = max(ready, key=lambda item: item[1])
            start = index * self.spec.slot_size
            payload = bytes(self._shm.buf[start : start + payload_size])
            return SharedFrameRecord(generation, sequence, captured_at_ms, self.spec.map_instance, payload)

    def read(self, sequence: int) -> SharedFrameRecord | None:
        """Return one exact sequence without falling back to an older frame."""
        requested = int(sequence)
        if requested < 0:
            return None
        with self._locked():
            for state, item_sequence, captured_at_ms, index, generation, payload_size in self._entries():
                if state != _STATE_READY or item_sequence != requested:
                    continue
                start = index * self.spec.slot_size
                payload = bytes(self._shm.buf[start : start + payload_size])
                return SharedFrameRecord(generation, item_sequence, captured_at_ms, self.spec.map_instance, payload)
        return None

    def clear(self) -> None:
        """Discard all slots while preserving the shared-memory allocation."""
        with self._locked():
            for index in range(self.spec.capacity):
                self._set_meta(index, state=_STATE_EMPTY, sequence=-1)

    def rebind_session(self, *, map_instance: str) -> None:
        """Reuse the ring for a new map instance without allocating another block."""
        instance = str(map_instance).strip()
        if not instance:
            raise ValueError("map_instance is required")
        with self._locked():
            self.spec = replace(self.spec, map_instance=instance)
            for index in range(self.spec.capacity):
                self._set_meta(index, state=_STATE_EMPTY, sequence=-1)

    def close(self, *, unlink: bool = False) -> None:
        name = self.spec.name
        shm = self._shm
        if shm is not None:
            self._shm = None
            shm.close()
        if unlink and not self._unlinked:
            try:
                SharedMemory(name=name).unlink()
            except FileNotFoundError:
                pass
            finally:
                self._unlinked = True

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
