"""Read-only PoE2 player/entity memory probe for live terrain validation.

This is deliberately an experiment tool.  It opens the game with
PROCESS_VM_READ|PROCESS_QUERY_INFORMATION only, resolves the same validated
layout used by the terrain producer, samples the local player's Render
component, and writes a JSON record beside the terrain sample.  It never
writes to the game process and never sends input.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import struct
import sys
import time
from typing import Any

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
POE2_RESEARCH_ROOT = Path("D:/ACloud/poe2-map-research")
if str(POE2_RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(POE2_RESEARCH_ROOT))

from windows_capture import (  # noqa: E402
    POE2_LAYOUT,
    ProcessReader,
    find_process_id,
    resolve_poe2_descriptor,
    resolve_poe2_layout,
)


POINTER_MIN = 0x10000
POINTER_MAX = 0x7FFFFFFFFFFF
COMPONENT_LOOKUP_OFFSET = 0x28
COMPONENT_VECTOR_OFFSET = 0x10
COMPONENT_ENTRY_STRIDE = 0x10
COMPONENT_NAME_OFFSET = 0x00
COMPONENT_INDEX_OFFSET = 0x08
RENDER_POSITION_OFFSET = 0x138
WORLD_TO_GRID = 23.0 / 250.0


class ProbeError(RuntimeError):
    """A diagnostic failure that should be recorded rather than hidden."""


def _pointer(value: int) -> bool:
    return POINTER_MIN <= value <= POINTER_MAX and value % 8 == 0


def _data_address(value: int) -> bool:
    """Native string buffers may be byte-aligned even when objects are not."""
    return POINTER_MIN <= value <= POINTER_MAX


def _read_ptr(reader: ProcessReader, address: int) -> int:
    return struct.unpack("<Q", reader.read(address, 8))[0]


def _read_i32(reader: ProcessReader, address: int) -> int:
    return struct.unpack("<i", reader.read(address, 4))[0]


def _read_f32_triplet(reader: ProcessReader, address: int) -> tuple[float, float, float]:
    values = struct.unpack("<fff", reader.read(address, 12))
    return (float(values[0]), float(values[1]), float(values[2]))


def _read_utf8_z(reader: ProcessReader, address: int, maximum: int = 128) -> str | None:
    if not _data_address(address):
        return None
    raw = bytearray()
    for offset in range(0, maximum, 32):
        chunk = reader.read(address + offset, min(32, maximum - offset))
        if b"\0" in chunk:
            raw.extend(chunk.split(b"\0", 1)[0])
            break
        raw.extend(chunk)
    if not raw:
        return None
    return raw.decode("utf-8", errors="replace")


def _read_utf16_z(reader: ProcessReader, address: int, maximum_characters: int = 256) -> str | None:
    if not _data_address(address):
        return None
    raw = bytearray()
    for offset in range(0, maximum_characters * 2, 32):
        chunk = reader.read(address + offset, min(32, maximum_characters * 2 - offset))
        for index in range(0, len(chunk) - 1, 2):
            pair = chunk[index : index + 2]
            if pair == b"\0\0":
                return raw.decode("utf-16-le", errors="replace") if raw else None
            raw.extend(pair)
    return raw.decode("utf-16-le", errors="replace") if raw else None


def _read_native_wstring(reader: ProcessReader, address: int) -> str | None:
    """Read the std::wstring layout used by the validated terrain resolver."""
    try:
        size = struct.unpack("<Q", reader.read(address + 16, 8))[0]
        capacity = struct.unpack("<Q", reader.read(address + 24, 8))[0]
        if not 0 < size <= 4096 or capacity < size:
            return None
        data_address = address if capacity < 8 else _read_ptr(reader, address)
        raw = reader.read(data_address, min(size, 256) * 2)
        return raw.decode("utf-16-le", errors="replace")
    except (OSError, ValueError, struct.error):
        return None


def _read_vector(reader: ProcessReader, address: int) -> tuple[int, int]:
    begin = _read_ptr(reader, address)
    end = _read_ptr(reader, address + 8)
    if not _pointer(begin) or end < begin or end - begin > 0x100000:
        raise ProbeError(f"invalid vector at 0x{address:X}: begin=0x{begin:X} end=0x{end:X}")
    return begin, end


def enumerate_components(reader: ProcessReader, player: int, details: int) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Resolve the type name table into component names and live addresses."""
    lookup = _read_ptr(reader, details + COMPONENT_LOOKUP_OFFSET)
    if not _pointer(lookup):
        raise ProbeError(f"component lookup pointer is invalid: 0x{lookup:X}")
    names_begin, names_end = _read_vector(reader, lookup + COMPONENT_LOOKUP_OFFSET)
    component_begin, component_end = _read_vector(reader, player + COMPONENT_VECTOR_OFFSET)
    component_count = (component_end - component_begin) // 8
    if component_count > 512:
        raise ProbeError(f"component vector is implausibly large: {component_count}")

    records: list[dict[str, Any]] = []
    addresses: dict[str, int] = {}
    entry_count = (names_end - names_begin) // COMPONENT_ENTRY_STRIDE
    if entry_count > 512:
        raise ProbeError(f"component lookup is implausibly large: {entry_count}")
    for index in range(entry_count):
        entry = names_begin + index * COMPONENT_ENTRY_STRIDE
        try:
            name = _read_utf8_z(reader, _read_ptr(reader, entry + COMPONENT_NAME_OFFSET))
            slot = _read_i32(reader, entry + COMPONENT_INDEX_OFFSET)
            component = _read_ptr(reader, component_begin + slot * 8) if 0 <= slot < component_count else 0
        except (OSError, ProbeError, struct.error) as exc:
            records.append({"entry": index, "error": f"{type(exc).__name__}: {exc}"})
            continue
        if not name:
            continue
        item = {"entry": index, "name": name, "slot": slot, "address": f"0x{component:X}"}
        records.append(item)
        if _pointer(component):
            addresses[name] = component
    return records, addresses


def _json_value(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    return value


def load_terrain(terrain_path: Path, manifest_path: Path | None = None) -> dict[str, Any]:
    archive = np.load(terrain_path, allow_pickle=False)
    arrays = {key: archive[key] for key in archive.files if key != "metadata_json"}
    metadata: dict[str, Any] = {}
    if "metadata_json" in archive.files:
        raw = archive["metadata_json"]
        metadata = json.loads(str(raw.item() if raw.ndim == 0 else raw))
    if manifest_path and manifest_path.is_file():
        metadata["archive_manifest"] = json.loads(manifest_path.read_text(encoding="utf-8"))
    shape = arrays.get("raw_cells", np.empty((0, 0))).shape
    return {"path": str(terrain_path.resolve()), "metadata": metadata, "shape": list(shape), "arrays": arrays}


def terrain_neighbourhood(terrain: dict[str, Any], grid: tuple[float, float], radius: int = 3) -> dict[str, Any]:
    arrays = terrain["arrays"]
    height, width = terrain["shape"]
    x, y = grid
    cx, cy = int(round(x)), int(round(y))
    x0, x1 = max(0, cx - radius), min(width, cx + radius + 1)
    y0, y1 = max(0, cy - radius), min(height, cy + radius + 1)
    result: dict[str, Any] = {
        "center_grid": [cx, cy],
        "bounds_xyxy": [x0, y0, x1, y1],
        "in_bounds": 0 <= x < width and 0 <= y < height,
    }
    for name, array in arrays.items():
        if array.ndim == 2:
            result[name] = array[y0:y1, x0:x1].tolist()
    return result


def run_probe(
    output_directory: str | Path,
    terrain_path: str | Path,
    *,
    sample_count: int = 8,
    interval_seconds: float = 0.05,
) -> dict[str, Any]:
    output = Path(output_directory).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    terrain_file = Path(terrain_path).expanduser().resolve()
    terrain = load_terrain(terrain_file, terrain_file.with_name("latest.json"))
    captured_at = datetime.now(timezone.utc).isoformat()
    errors: list[str] = []

    pid = find_process_id()
    descriptor = resolve_poe2_descriptor(pid, stage="player-memory-probe")
    process_identity = descriptor["process"]
    resolved_slot = int(descriptor["resolved_global_slot_rva"], 16)
    samples: list[dict[str, Any]] = []
    component_records: list[dict[str, Any]] = []
    player_metadata: str | None = None
    addresses: dict[str, Any] = {}
    layout_snapshot: dict[str, Any] = {}

    with ProcessReader(pid) as reader:
        module_base = reader.module_base()
        layout = resolve_poe2_layout(reader, module_base, resolved_slot)
        player = int(layout["player"])
        details = _read_ptr(reader, player + POE2_LAYOUT["entity_details"])
        player_metadata = _read_native_wstring(reader, details + POE2_LAYOUT["details_metadata"])
        addresses.update({
            "module_base": f"0x{module_base:X}",
            "slot": f"0x{layout['slot']:X}",
            "root": f"0x{layout['root']:X}",
            "state": f"0x{layout['state']:X}",
            "area": f"0x{layout['area']:X}",
            "player": f"0x{player:X}",
            "details": f"0x{details:X}",
            "terrain": f"0x{layout['terrain']:X}",
            "buffer_start": f"0x{layout['buffer_start']:X}",
            "buffer_end": f"0x{layout['buffer_end']:X}",
        })
        layout_snapshot = {
            "area_id": layout["area_code"],
            "area_hash": f"{layout['area_hash']:08X}",
            "width": layout["width"],
            "height": layout["height"],
            "bytes_per_row": layout["bytes_per_row"],
        }
        try:
            component_records, component_addresses = enumerate_components(reader, player, details)
            addresses["components"] = {name: f"0x{address:X}" for name, address in component_addresses.items()}
        except Exception as exc:
            errors.append(f"component enumeration failed: {type(exc).__name__}: {exc}")
            component_addresses = {}

        render = component_addresses.get("Render")
        if not render:
            errors.append("Render component was not resolved")
        else:
            for index in range(max(1, int(sample_count))):
                try:
                    world = _read_f32_triplet(reader, render + RENDER_POSITION_OFFSET)
                    grid = (world[0] * WORLD_TO_GRID, world[1] * WORLD_TO_GRID)
                    samples.append({
                        "index": index,
                        "world": list(world),
                        "grid": list(grid),
                        "in_bounds": 0 <= grid[0] < terrain["shape"][1] and 0 <= grid[1] < terrain["shape"][0],
                    })
                except Exception as exc:
                    errors.append(f"position sample {index} failed: {type(exc).__name__}: {exc}")
                if index + 1 < sample_count:
                    time.sleep(max(0.0, interval_seconds))

    if samples:
        final_grid = (
            float(samples[-1]["grid"][0]),
            float(samples[-1]["grid"][1]),
        )
        neighbourhood = terrain_neighbourhood(terrain, final_grid)
    else:
        neighbourhood = {"in_bounds": False, "reason": "no position samples"}

    terrain_metadata = terrain["metadata"]
    result: dict[str, Any] = {
        "schema_version": 1,
        "tool": "poe2-player-memory-probe",
        "captured_at": captured_at,
        "read_only": True,
        "process": process_identity,
        "client_build": descriptor["metadata"].get("client_build"),
        "descriptor": {
            "module_base": descriptor["module_base"],
            "resolved_global_slot_rva": descriptor["resolved_global_slot_rva"],
            "metadata": descriptor["metadata"],
        },
        "addresses": addresses,
        "layout": layout_snapshot,
        "player_metadata": player_metadata,
        "components": component_records,
        "position": {
            "samples": samples,
            "coordinate_formula": "grid_x = world_x * 23 / 250; grid_y = world_y * 23 / 250",
            "world_to_grid": [[WORLD_TO_GRID, 0.0, 0.0], [0.0, WORLD_TO_GRID, 0.0]],
        },
        "terrain": {
            "path": terrain["path"],
            "shape": terrain["shape"],
            "metadata": terrain_metadata,
            "neighbourhood": neighbourhood,
        },
        "cross_checks": {
            "instance_id_match": descriptor["metadata"].get("instance_id") == terrain_metadata.get("instance_id"),
            "area_id_match": descriptor["metadata"].get("area_id") == terrain_metadata.get("area_id"),
            "area_hash_match": descriptor["metadata"].get("area_hash") == terrain_metadata.get("area_hash"),
            "shape_match": [layout_snapshot.get("height"), layout_snapshot.get("width")] == terrain["shape"],
            "terrain_captured_at": terrain_metadata.get("captured_at"),
        },
        "errors": errors,
    }

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    timestamped = output / f"player-memory-probe-{stamp}.json"
    latest = output / "player-memory-probe-latest.json"
    payload = json.dumps(result, ensure_ascii=False, indent=2, default=_json_value) + "\n"
    timestamped.write_text(payload, encoding="utf-8")
    latest.write_text(payload, encoding="utf-8")
    result["saved"] = {"timestamped": str(timestamped), "latest": str(latest)}
    return result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(PROJECT_ROOT / "data/poe2_live_terrain_test/memory_probes"))
    parser.add_argument("--terrain", default="D:/ACloud/poe2-map-research/experiments/live-terrain-preview/output/latest.npz")
    parser.add_argument("--samples", type=int, default=8)
    parser.add_argument("--interval", type=float, default=0.05)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = run_probe(args.out, args.terrain, sample_count=max(1, args.samples), interval_seconds=args.interval)
    except Exception as exc:
        print(json.dumps({"tool": "poe2-player-memory-probe", "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False))
        return 2
    print(json.dumps({
        "saved": result["saved"],
        "instance_id": result["descriptor"]["metadata"].get("instance_id"),
        "player_metadata": result["player_metadata"],
        "component_count": len(result["components"]),
        "render_address": result["addresses"].get("components", {}).get("Render"),
        "position_samples": result["position"]["samples"],
        "cross_checks": result["cross_checks"],
        "errors": result["errors"],
    }, ensure_ascii=False, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
