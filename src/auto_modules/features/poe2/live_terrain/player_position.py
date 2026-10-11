"""One-shot read-only player position for the PoE2 live-terrain experiment."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
from pathlib import Path
import struct
import sys
from typing import Any


POE2_RESEARCH_ROOT = Path("D:/ACloud/poe2-map-research")
if str(POE2_RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(POE2_RESEARCH_ROOT))

from windows_capture import (  # type: ignore[import-not-found]  # noqa: E402
    POE2_LAYOUT,
    ProcessReader,
    find_process_id,
    resolve_poe2_descriptor,
    resolve_poe2_layout,
)


WORLD_TO_GRID = 23.0 / 250.0
COMPONENT_LOOKUP_OFFSET = 0x28
COMPONENT_VECTOR_OFFSET = 0x10
COMPONENT_ENTRY_STRIDE = 0x10
RENDER_POSITION_OFFSET = 0x138
POINTER_MIN = 0x10000
POINTER_MAX = 0x7FFFFFFFFFFF


class PlayerPositionError(RuntimeError):
    """The current client did not provide a validated player position."""


@dataclass(frozen=True)
class PlayerPositionSample:
    world: tuple[float, float, float]
    grid: tuple[float, float]
    captured_at: str
    area_instance: str

    @classmethod
    def from_world(
        cls,
        *,
        world: tuple[float, float, float] | list[float],
        captured_at: str,
        area_instance: str,
    ) -> "PlayerPositionSample":
        values = tuple(float(value) for value in world)
        if len(values) != 3 or not all(math.isfinite(value) for value in values):
            raise ValueError("world position values must be finite")
        if not area_instance:
            raise ValueError("area_instance is required")
        return cls(
            world=(values[0], values[1], values[2]),
            grid=(values[0] * WORLD_TO_GRID, values[1] * WORLD_TO_GRID),
            captured_at=str(captured_at),
            area_instance=str(area_instance),
        )


def _plausible_pointer(value: int) -> bool:
    return POINTER_MIN <= value <= POINTER_MAX and value % 8 == 0


def _read_pointer(reader: Any, address: int) -> int:
    return struct.unpack("<Q", reader.read(address, 8))[0]


def _read_i32(reader: Any, address: int) -> int:
    return struct.unpack("<i", reader.read(address, 4))[0]


def _read_utf8(reader: Any, address: int, maximum: int = 128) -> str | None:
    if not POINTER_MIN <= address <= POINTER_MAX:
        return None
    raw = reader.read(address, maximum)
    return raw.split(b"\0", 1)[0].decode("utf-8", errors="replace") or None


def _read_vector(reader: Any, address: int) -> tuple[int, int]:
    begin = _read_pointer(reader, address)
    end = _read_pointer(reader, address + 8)
    if not _plausible_pointer(begin) or end < begin or (end - begin) % 8:
        raise PlayerPositionError("invalid component vector")
    return begin, end


def resolve_component_addresses(
    reader: Any,
    player: int,
    details: int,
    *,
    component_name_cache: dict[int, dict[str, int]] | None = None,
) -> dict[str, int]:
    """Resolve component addresses while optionally reusing static name slots."""
    lookup = _read_pointer(reader, details + COMPONENT_LOOKUP_OFFSET)
    if not _plausible_pointer(lookup):
        raise PlayerPositionError("component lookup is unavailable")
    names_begin, names_end = _read_vector(reader, lookup + COMPONENT_LOOKUP_OFFSET)
    components_begin, components_end = _read_vector(reader, player + COMPONENT_VECTOR_OFFSET)
    component_count = (components_end - components_begin) // 8
    if component_count > 512 or (names_end - names_begin) // COMPONENT_ENTRY_STRIDE > 512:
        raise PlayerPositionError("component table is implausibly large")

    static_slots = None if component_name_cache is None else component_name_cache.get(int(lookup))
    if static_slots is None:
        static_slots = {}
        for offset in range(0, names_end - names_begin, COMPONENT_ENTRY_STRIDE):
            entry = names_begin + offset
            name_pointer = _read_pointer(reader, entry)
            name = _read_utf8(reader, name_pointer)
            if not name:
                continue
            slot = _read_i32(reader, entry + 8)
            if 0 <= slot < component_count:
                static_slots[name] = slot
        if component_name_cache is not None:
            component_name_cache[int(lookup)] = dict(static_slots)
    result: dict[str, int] = {}
    for name, slot in static_slots.items():
        component = _read_pointer(reader, components_begin + slot * 8)
        if _plausible_pointer(component):
            result[name] = component
    return result


class Poe2PlayerPositionSource:
    """Read one player position from the currently validated PoE2 session."""

    def __init__(self, *, api: Any | None = None) -> None:
        self.api = api

    def read_once(self, expected_instance_id: str | None = None) -> PlayerPositionSample:
        api = self.api
        find_pid = getattr(api, "find_process_id", find_process_id) if api is not None else find_process_id
        resolve_descriptor = (
            getattr(api, "resolve_poe2_descriptor", resolve_poe2_descriptor)
            if api is not None
            else resolve_poe2_descriptor
        )
        reader_type = getattr(api, "ProcessReader", ProcessReader) if api is not None else ProcessReader
        resolve_layout = getattr(api, "resolve_poe2_layout", resolve_poe2_layout) if api is not None else resolve_poe2_layout

        pid = find_pid()
        descriptor = resolve_descriptor(pid, stage="player-position")
        resolved_slot = int(descriptor["resolved_global_slot_rva"], 16)
        with reader_type(pid) as reader:
            layout = resolve_layout(reader, reader.module_base(), resolved_slot)
            area_instance = f"{layout['area_code']}:{layout['area_hash']:08X}"
            if expected_instance_id and area_instance != expected_instance_id:
                raise PlayerPositionError(
                    f"area instance changed during position read: expected {expected_instance_id}, got {area_instance}"
                )
            player = int(layout["player"])
            details = _read_pointer(reader, player + POE2_LAYOUT["entity_details"])
            components = resolve_component_addresses(reader, player, details)
            render = components.get("Render")
            if not render:
                raise PlayerPositionError("local player Render component is unavailable")
            world = struct.unpack("<fff", reader.read(render + RENDER_POSITION_OFFSET, 12))
        return PlayerPositionSample.from_world(
            world=world,
            captured_at=datetime.now(timezone.utc).isoformat(),
            area_instance=area_instance,
        )


__all__ = [
    "PlayerPositionError",
    "PlayerPositionSample",
    "Poe2PlayerPositionSource",
    "RENDER_POSITION_OFFSET",
    "WORLD_TO_GRID",
    "resolve_component_addresses",
]
