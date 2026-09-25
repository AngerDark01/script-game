"""Anchor-bounded first-frame registration experiment for PoE2 terrain samples."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import math
import os
from pathlib import Path
import shutil
import sys
from typing import Any, Mapping, Sequence
import uuid

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.absolute_registrar import (
    AnchorLocalProbeConfig,
    AnchorLocalProbeInput,
    AnchorLocalProbeResult,
    AnchoredCandidate,
    crop_terrain_around_anchor,
    match_anchor_local,
    prepare_local_feature,
)
from auto_modules.features.poe2.live_terrain.orientation import TerrainOrientation
from tools.debug.poe2_live_terrain_localization_probe import _candidate_overlay

def _read_image(path: Path, mode: int) -> np.ndarray:
    image = cv2.imread(str(path), mode)
    if image is None or image.size == 0:
        raise ValueError(f"could not read sample image: {path}")
    return image


def load_anchor_probe_input(sample_directory: str | Path) -> AnchorLocalProbeInput:
    root = Path(sample_directory).expanduser().resolve()
    manifest = json.loads((root / "sample.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("sample manifest must be a JSON object")
    terrain_details = manifest.get("terrain")
    position_details = manifest.get("player_position")
    if not isinstance(terrain_details, dict) or terrain_details.get("status") != "available":
        raise ValueError("sample terrain must be available")
    if not isinstance(position_details, dict) or position_details.get("status") != "available":
        raise ValueError("sample player position must be available")
    terrain_instance = str(terrain_details.get("instance_id", ""))
    position_instance = str(position_details.get("area_instance", ""))
    if not terrain_instance or terrain_instance != position_instance:
        raise ValueError("terrain and player position must use the same area instance")

    terrain = _read_image(root / "terrain.png", cv2.IMREAD_COLOR)
    anchor = position_details.get("terrain_grid")
    if anchor is None:
        anchor = position_details.get("grid")
        monitor_config = dict(manifest.get("monitor_config", {}))
        orientation = TerrainOrientation()
        if not orientation.is_identity and isinstance(anchor, (list, tuple)) and len(anchor) == 2:
            native_height = int(
                terrain_details.get("native_height", terrain_details.get("height", 0))
            )
            native_width = int(
                terrain_details.get("native_width", terrain_details.get("width", 0))
            )
            if native_height < 1 or native_width < 1:
                raise ValueError("terrain native dimensions must be positive")
            anchor = orientation.transform_point(anchor, (native_height, native_width))
    if not isinstance(anchor, (list, tuple)) or len(anchor) != 2:
        raise ValueError("player position grid must contain two values")
    anchor_grid = (float(anchor[0]), float(anchor[1]))
    if not all(math.isfinite(value) for value in anchor_grid):
        raise ValueError("player position grid must be finite")
    if not (0.0 <= anchor_grid[0] < terrain.shape[1] and 0.0 <= anchor_grid[1] < terrain.shape[0]):
        raise ValueError("player position grid must be inside terrain image")
    if terrain_details.get("coordinate_space") == "oriented-preview" and (
        int(terrain_details.get("width", -1)) != terrain.shape[1]
        or int(terrain_details.get("height", -1)) != terrain.shape[0]
    ):
        raise ValueError("terrain manifest dimensions must match terrain image")

    binding = dict(manifest.get("monitor_config", {})).get("binding", {})
    marker = dict(binding).get("player_marker_position") if isinstance(binding, dict) else None
    feature_path = root / "wall_mask.png"
    if not feature_path.is_file():
        feature_path = root / "feature.png"
    feature = _read_image(feature_path, cv2.IMREAD_GRAYSCALE)
    if isinstance(marker, (list, tuple)) and len(marker) == 2:
        local_player = (float(marker[0]), float(marker[1]))
    else:
        local_player = (feature.shape[1] / 2.0, feature.shape[0] / 2.0)
    if not all(math.isfinite(value) for value in local_player):
        raise ValueError("local player position must be finite")
    if not (
        0.0 <= local_player[0] < feature.shape[1]
        and 0.0 <= local_player[1] < feature.shape[0]
    ):
        raise ValueError("local player position must be inside feature image")
    return AnchorLocalProbeInput(
        sample_root=root,
        manifest=manifest,
        terrain=terrain,
        feature=feature,
        local_player=local_player,
        anchor_grid=anchor_grid,
    )

def save_probe_diagnostics(
    probe_input: AnchorLocalProbeInput,
    result: AnchorLocalProbeResult,
    output_directory: str | Path,
    *,
    config: AnchorLocalProbeConfig,
) -> Path:
    output = Path(output_directory).expanduser().resolve()
    if output.exists():
        raise FileExistsError(f"diagnostic output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.parent / f".{output.name}.{uuid.uuid4().hex}.tmp"
    temporary.mkdir()
    try:
        if not cv2.imwrite(str(temporary / "local_terrain.png"), result.local_terrain):
            raise OSError("failed to save local_terrain.png")
        if not cv2.imwrite(str(temporary / "prepared_feature.png"), result.prepared_feature):
            raise OSError("failed to save prepared_feature.png")
        if result.best is not None:
            overlay = _candidate_overlay(
                result.local_terrain,
                result.prepared_feature,
                probe_input.local_player,
                result.best.registration,
            )
            if not cv2.imwrite(str(temporary / "best_overlay.png"), overlay):
                raise OSError("failed to save best_overlay.png")
        report = {
            "sample": str(probe_input.sample_root) if probe_input.sample_root else None,
            "status": result.status,
            "reason": result.reason,
            "anchor_grid": list(result.anchor_grid),
            "crop_bounds": list(result.crop_bounds),
            "config": asdict(config),
            "best": result.best.as_dict(1) if result.best is not None else None,
            "confidence": (
                None
                if result.best is None or result.status != "anchored_candidate"
                else float(min(1.0, max(0.0, result.best.anchored_score)))
            ),
            "candidates": [item.as_dict(index) for index, item in enumerate(result.candidates, 1)],
        }
        (temporary / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return output


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Match one PoE2 minimap frame inside a memory-anchored terrain crop.",
    )
    parser.add_argument("--sample", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--crop-radius", type=int, default=150)
    parser.add_argument("--refine-crop-radius", type=int, default=110)
    parser.add_argument("--top-exclusion-rows", type=int, default=40)
    parser.add_argument("--max-anchor-error", type=float, default=80.0)
    parser.add_argument("--anchor-weight", type=float, default=0.65)
    parser.add_argument("--minimum-confidence", type=float, default=0.80)
    parser.add_argument("--anchor-disambiguation-gap", type=float, default=1.0)
    parser.add_argument("--minimum-score", type=float, default=0.50)
    parser.add_argument("--minimum-forward-coverage", type=float, default=0.65)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)
    config = AnchorLocalProbeConfig(
        crop_radius=args.crop_radius,
        refine_crop_radius=args.refine_crop_radius,
        top_exclusion_rows=args.top_exclusion_rows,
        max_anchor_error=args.max_anchor_error,
        anchor_weight=args.anchor_weight,
        minimum_confidence=args.minimum_confidence,
        anchor_disambiguation_gap=args.anchor_disambiguation_gap,
        minimum_score=args.minimum_score,
        minimum_forward_coverage=args.minimum_forward_coverage,
    )
    probe_input = load_anchor_probe_input(args.sample)
    result = match_anchor_local(probe_input, config)
    output = save_probe_diagnostics(probe_input, result, args.output, config=config)
    print(json.dumps({"status": result.status, "reason": result.reason, "output": str(output)}, ensure_ascii=False))
    return 0 if result.status != "rejected" else 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "AnchorLocalProbeConfig",
    "AnchorLocalProbeInput",
    "AnchorLocalProbeResult",
    "AnchoredCandidate",
    "crop_terrain_around_anchor",
    "load_anchor_probe_input",
    "match_anchor_local",
    "prepare_local_feature",
    "save_probe_diagnostics",
]
