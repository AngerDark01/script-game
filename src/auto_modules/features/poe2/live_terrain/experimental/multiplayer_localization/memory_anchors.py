"""Read-only two-player PoE2 memory adapter for the localization experiment."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import struct
import sys
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from auto_modules.features.poe2.live_terrain.orientation import TerrainOrientation
from auto_modules.features.poe2.live_terrain.player_position import (
    POINTER_MAX,
    POINTER_MIN,
    RENDER_POSITION_OFFSET,
    WORLD_TO_GRID,
    PlayerPositionError,
    resolve_component_addresses,
)

from ..hybrid_localization.memory_anchor import parse_timestamp_ms
from ..hybrid_localization.models import PositionAnchor


POE2_RESEARCH_ROOT = "D:/ACloud/poe2-map-research"
if POE2_RESEARCH_ROOT not in sys.path:
    sys.path.insert(0, POE2_RESEARCH_ROOT)

from windows_capture import (  # type: ignore[import-not-found]  # noqa: E402
    POE2_LAYOUT,
    ProcessReader,
    find_process_id,
    resolve_poe2_descriptor,
    resolve_poe2_layout,
)


# This is an experiment-only contract observed in the current PoE2 build.  It
# is intentionally not added to the single-player source until version checks
# and more map samples establish that the entity vector is stable.
ENTITY_VECTOR_OFFSET = 0x5B8
MAX_ENTITY_COUNT = 64
_LOGGER = logging.getLogger(__name__)


class _CountingReader:
    """Proxy a process reader while preserving the exact read contract."""

    def __init__(self, reader: Any) -> None:
        self._reader = reader
        self.read_calls = 0
        self.read_bytes = 0

    def read(self, pointer: int, size: int) -> bytes:
        self.read_calls += 1
        self.read_bytes += int(size)
        return self._reader.read(pointer, size)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._reader, name)


@dataclass(frozen=True)
class Poe2EntityPositionSample:
    identity: str
    metadata: str
    world: tuple[float, float, float]
    grid: tuple[float, float]
    captured_at: str
    area_instance: str
    entity_address: int


def _pointer(value: int) -> bool:
    return POINTER_MIN <= int(value) <= POINTER_MAX and int(value) % 8 == 0


def _read_pointer(reader: Any, address: int) -> int:
    return struct.unpack("<Q", reader.read(address, 8))[0]


def _read_vector(reader: Any, address: int) -> tuple[int, int]:
    begin = _read_pointer(reader, address)
    end = _read_pointer(reader, address + 8)
    if not _pointer(begin) or end < begin or (end - begin) % 8:
        raise PlayerPositionError("invalid dual-player entity vector")
    count = (end - begin) // 8
    if count > MAX_ENTITY_COUNT:
        raise PlayerPositionError("dual-player entity vector is implausibly large")
    return begin, end


def _read_native_wstring(reader: Any, address: int) -> str | None:
    try:
        size = struct.unpack("<Q", reader.read(address + 16, 8))[0]
        capacity = struct.unpack("<Q", reader.read(address + 24, 8))[0]
        if not 0 < size <= 4096 or capacity < size:
            return None
        data_address = address if capacity < 8 else _read_pointer(reader, address)
        if not _pointer(data_address):
            return None
        raw = reader.read(data_address, min(size, 256) * 2)
        return raw.decode("utf-16-le", errors="replace") or None
    except (OSError, ValueError, struct.error):
        return None


def _read_world(reader: Any, render: int) -> tuple[float, float, float]:
    values = struct.unpack("<fff", reader.read(render + RENDER_POSITION_OFFSET, 12))
    world = tuple(float(value) for value in values)
    if not all(value == value and abs(value) < 1e9 for value in world):
        raise PlayerPositionError("dual-player Render position is invalid")
    return world  # type: ignore[return-value]


def _identity_for(metadata: str, index: int, used: set[str]) -> str:
    base = metadata or f"entity-{index}"
    identity = base
    suffix = 2
    while identity in used:
        identity = f"{base}#{suffix}"
        suffix += 1
    used.add(identity)
    return identity


class Poe2DualPlayerPositionSource:
    """Read the two visible player entities in one read-only process session."""

    def __init__(self, *, api: Any | None = None, max_players: int = 2) -> None:
        self.api = api
        self.max_players = int(max_players)
        self._cached_pid: int | None = None
        self._cached_descriptor: Mapping[str, Any] | None = None
        self._cached_layout_pid: int | None = None
        self._cached_layout_slot: int | None = None
        self._cached_layout: Mapping[str, Any] | None = None
        self._component_name_cache: dict[int, dict[str, int]] = {}
        self.last_read_diagnostics: dict[str, Any] = {}
        if self.max_players != 2:
            raise ValueError("the experimental adapter currently supports exactly two players")

    def read_many(self, expected_instance_id: str | None = None) -> tuple[Poe2EntityPositionSample, ...]:
        api = self.api
        find_pid = getattr(api, "find_process_id", find_process_id) if api is not None else find_process_id
        resolve_descriptor = (
            getattr(api, "resolve_poe2_descriptor", resolve_poe2_descriptor)
            if api is not None
            else resolve_poe2_descriptor
        )
        reader_type = getattr(api, "ProcessReader", ProcessReader) if api is not None else ProcessReader
        resolve_layout = (
            getattr(api, "resolve_poe2_layout", resolve_poe2_layout)
            if api is not None
            else resolve_poe2_layout
        )
        started = time.perf_counter()
        stage_started = started
        pid = find_pid()
        find_pid_ms = (time.perf_counter() - stage_started) * 1000.0
        descriptor_cache_hit = self._cached_pid == pid and self._cached_descriptor is not None
        if self._cached_pid != pid or self._cached_descriptor is None:
            stage_started = time.perf_counter()
            descriptor = resolve_descriptor(pid, stage="dual-player-position")
            descriptor_ms = (time.perf_counter() - stage_started) * 1000.0
            self._cached_pid = int(pid)
            self._cached_descriptor = dict(descriptor)
            self._component_name_cache.clear()
        else:
            descriptor = self._cached_descriptor
            descriptor_ms = 0.0
        resolved_slot = int(descriptor["resolved_global_slot_rva"], 16)
        captured_at = datetime.now(timezone.utc).isoformat()
        reader_started = time.perf_counter()
        with reader_type(pid) as raw_reader:
            reader = _CountingReader(raw_reader)
            module_base = reader.module_base()
            module_ms = (time.perf_counter() - reader_started) * 1000.0
            layout = None
            layout_cache_hit = (
                self._cached_layout_pid == int(pid)
                and self._cached_layout_slot == resolved_slot
                and self._cached_layout is not None
            )
            layout_started = time.perf_counter()
            if (
                layout_cache_hit
            ):
                layout = self._cached_layout
            if layout is None:
                layout = resolve_layout(reader, module_base, resolved_slot)
                self._cached_layout_pid = int(pid)
                self._cached_layout_slot = resolved_slot
                self._cached_layout = dict(layout)
            layout_ms = (time.perf_counter() - layout_started) * 1000.0
            area_instance = f"{layout['area_code']}:{layout['area_hash']:08X}"
            if expected_instance_id and area_instance != expected_instance_id:
                # A map transition invalidates all pointer-derived cache state.
                self._cached_layout = None
                self._cached_layout_pid = None
                self._cached_layout_slot = None
                self._component_name_cache.clear()
                layout_started = time.perf_counter()
                layout = resolve_layout(reader, module_base, resolved_slot)
                layout_ms += (time.perf_counter() - layout_started) * 1000.0
                self._cached_layout_pid = int(pid)
                self._cached_layout_slot = resolved_slot
                self._cached_layout = dict(layout)
                area_instance = f"{layout['area_code']}:{layout['area_hash']:08X}"
            if expected_instance_id and area_instance != expected_instance_id:
                raise PlayerPositionError(
                    f"area instance changed during dual-player read: expected {expected_instance_id}, got {area_instance}"
                )
            area = int(layout["area"])
            entity_scan_started = time.perf_counter()
            begin, end = _read_vector(reader, area + ENTITY_VECTOR_OFFSET)
            samples: list[Poe2EntityPositionSample] = []
            used: set[str] = set()
            entity_count = (end - begin) // 8
            scanned_entities = 0
            metadata_candidates = 0
            component_resolves = 0
            for index in range(entity_count):
                scanned_entities += 1
                entity = _read_pointer(reader, begin + index * 8)
                if not _pointer(entity):
                    continue
                details = _read_pointer(reader, entity + POE2_LAYOUT["entity_details"])
                if not _pointer(details):
                    continue
                metadata = _read_native_wstring(
                    reader,
                    details + POE2_LAYOUT["details_metadata"],
                )
                if not metadata or not metadata.startswith("Metadata/Characters/"):
                    continue
                metadata_candidates += 1
                component_resolves += 1
                components = resolve_component_addresses(
                    reader,
                    entity,
                    details,
                    component_name_cache=self._component_name_cache,
                )
                render = components.get("Render")
                if not render:
                    continue
                world = _read_world(reader, render)
                samples.append(
                    Poe2EntityPositionSample(
                        identity=_identity_for(metadata, index, used),
                        metadata=metadata,
                        world=world,
                        grid=(world[0] * WORLD_TO_GRID, world[1] * WORLD_TO_GRID),
                        captured_at=captured_at,
                        area_instance=area_instance,
                        entity_address=entity,
                    )
                )
                if len(samples) == self.max_players:
                    break
            entity_scan_ms = (time.perf_counter() - entity_scan_started) * 1000.0
            self.last_read_diagnostics = {
                "pid": int(pid),
                "expected_instance_id": expected_instance_id,
                "area_instance": area_instance,
                "find_pid_ms": find_pid_ms,
                "descriptor_ms": descriptor_ms,
                "descriptor_cache_hit": descriptor_cache_hit,
                "module_ms": module_ms,
                "layout_ms": layout_ms,
                "layout_cache_hit": layout_cache_hit,
                "entity_scan_ms": entity_scan_ms,
                "entity_count": entity_count,
                "scanned_entities": scanned_entities,
                "metadata_candidates": metadata_candidates,
                "component_resolves": component_resolves,
                "read_calls": reader.read_calls,
                "read_bytes": reader.read_bytes,
                "total_ms": (time.perf_counter() - started) * 1000.0,
                "sample_count": len(samples),
            }
            _LOGGER.info("step=dual_memory.read_timing diagnostics=%s", self.last_read_diagnostics)
        if len(samples) != self.max_players:
            raise PlayerPositionError(
                f"expected {self.max_players} player entities, found {len(samples)}"
            )
        return tuple(samples)


class Poe2DualMemoryAnchorProvider:
    """Convert one dual entity read into orientation-correct native anchors."""

    def __init__(
        self,
        source: Poe2DualPlayerPositionSource,
        orientation: TerrainOrientation,
        native_shape: tuple[int, int],
        clock_ms: Callable[[], int] | None = None,
    ) -> None:
        height, width = int(native_shape[0]), int(native_shape[1])
        if height <= 0 or width <= 0:
            raise ValueError("native_shape dimensions must be positive")
        self.source = source
        self.orientation = orientation
        self.native_shape = (height, width)
        self.clock_ms = clock_ms or (lambda: int(time.time() * 1000))
        self.read_count = 0

    def read_once(self, expected_instance_id: str) -> Mapping[str, PositionAnchor]:
        self.read_count += 1
        try:
            samples = self.source.read_many(expected_instance_id)
        except Exception:
            _LOGGER.exception(
                "step=dual_memory.read_failed read_count=%s expected_instance_id=%s diagnostics=%s",
                self.read_count,
                expected_instance_id,
                getattr(self.source, "last_read_diagnostics", {}),
            )
            raise
        _LOGGER.info(
            "step=dual_memory.read_success read_count=%s samples=%s diagnostics=%s",
            self.read_count,
            len(samples),
            getattr(self.source, "last_read_diagnostics", {}),
        )
        return {
            sample.identity: PositionAnchor(
                position=self.orientation.transform_point(sample.grid, self.native_shape),
                area_instance=sample.area_instance,
                captured_at_ms=parse_timestamp_ms(sample.captured_at, fallback=self.clock_ms),
                source="poe2_dual_memory",
            )
            for sample in samples
        }


__all__ = [
    "ENTITY_VECTOR_OFFSET",
    "MAX_ENTITY_COUNT",
    "Poe2DualMemoryAnchorProvider",
    "Poe2DualPlayerPositionSource",
    "Poe2EntityPositionSample",
]
