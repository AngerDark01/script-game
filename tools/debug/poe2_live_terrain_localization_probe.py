"""Offline PoE2 localization probe for saved screenshot/terrain samples.

This experiment deliberately stays outside the production runtime. It replays
the saved recognizer configuration, removes compact dynamic features, and
searches rotation, reflection, scale, and translation with Chamfer distance.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import logging
import math
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

import cv2
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from auto_modules.core.vision import HSVRecognizer


LOGGER = logging.getLogger("poe2.localization_probe")
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.similarity_search import (
    SearchCandidate,
    SimilaritySearchConfig as ProbeConfig,
    _binary_mask,
    clean_feature_mask,
    local_walkable_region,
    search_candidates,
    terrain_edges,
    terrain_walkable_mask,
    transform_feature,
)


@dataclass(frozen=True)
class ProbeSample:
    directory: Path
    manifest: Mapping[str, Any]
    raw: np.ndarray
    stored_feature: np.ndarray
    terrain: np.ndarray
    player_position: tuple[float, float]

def _read_image(path: Path, mode: int) -> np.ndarray:
    image = cv2.imread(str(path), mode)
    if image is None or image.size == 0:
        raise ValueError(f"could not read image: {path}")
    return image


def load_sample(directory: str | Path) -> ProbeSample:
    root = Path(directory).expanduser().resolve()
    manifest_path = root / "sample.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("sample manifest must be a JSON object")
    raw = _read_image(root / "raw.png", cv2.IMREAD_COLOR)
    stored_feature = _read_image(root / "feature.png", cv2.IMREAD_GRAYSCALE)
    terrain = _read_image(root / "terrain.png", cv2.IMREAD_COLOR)
    binding = dict(manifest.get("monitor_config", {})).get("binding", {})
    marker = dict(binding).get("player_marker_position")
    if isinstance(marker, (list, tuple)) and len(marker) == 2:
        player = (float(marker[0]), float(marker[1]))
    else:
        player = (raw.shape[1] / 2.0, raw.shape[0] / 2.0)
    return ProbeSample(root, manifest, raw, stored_feature, terrain, player)


def rebuild_feature(
    sample: ProbeSample,
    parameter_overrides: Mapping[str, Any] | None = None,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    recognizer = HSVRecognizer()
    params = dict(sample.manifest.get("monitor_config", {}).get("recognizer_params", {}))
    params.update(dict(parameter_overrides or {}))
    recognizer.set_params(params)
    processed = recognizer.preprocess_image(sample.raw)
    combined, _wall, _fog = recognizer.extract_combined(
        sample.raw,
        player_pos=(int(round(sample.player_position[0])), int(round(sample.player_position[1]))),
    )
    return processed, _binary_mask(combined), recognizer.get_params()

def _candidate_overlay(
    terrain: np.ndarray,
    feature: np.ndarray,
    player_position: tuple[float, float],
    candidate: SearchCandidate,
) -> np.ndarray:
    transformed = transform_feature(
        feature,
        player_position,
        angle=candidate.angle,
        reflect_horizontal=candidate.reflect_horizontal,
        scale=candidate.scale,
    )
    height, width = transformed.mask.shape
    x, y = candidate.top_left
    padding = max(36, min(180, max(height, width) // 2))
    crop_x = max(0, x - padding)
    crop_y = max(0, y - padding)
    crop_x2 = min(terrain.shape[1], x + width + padding)
    crop_y2 = min(terrain.shape[0], y + height + padding)
    gray = cv2.cvtColor(terrain, cv2.COLOR_BGR2GRAY) if terrain.ndim == 3 else terrain
    patch = gray[crop_y:crop_y2, crop_x:crop_x2].copy()
    overlay = cv2.cvtColor(patch, cv2.COLOR_GRAY2BGR)
    terrain_edge = terrain_edges(cv2.cvtColor(patch, cv2.COLOR_GRAY2BGR), border_clear=0) > 0
    template_edge = transformed.mask > 0
    template_canvas = np.zeros_like(patch, dtype=bool)
    template_x = x - crop_x
    template_y = y - crop_y
    template_canvas[
        template_y : template_y + height,
        template_x : template_x + width,
    ] = template_edge
    overlay[terrain_edge] = (255, 80, 40)
    overlay[template_canvas] = (40, 220, 40)
    overlay[terrain_edge & template_canvas] = (0, 255, 255)
    marker = (
        int(round(template_x + transformed.player_position[0])),
        int(round(template_y + transformed.player_position[1])),
    )
    cv2.drawMarker(overlay, marker, (0, 0, 255), cv2.MARKER_CROSS, 16, 2)
    cv2.putText(
        overlay,
        (
            f"score={candidate.score:.3f} angle={candidate.angle:.1f} "
            f"flip={int(candidate.reflect_horizontal)} scale={candidate.scale:.3f}"
        ),
        (8, 22),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.48,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )
    return overlay


def _candidate_map(terrain: np.ndarray, candidates: Sequence[SearchCandidate]) -> np.ndarray:
    canvas = terrain.copy() if terrain.ndim == 3 else cv2.cvtColor(terrain, cv2.COLOR_GRAY2BGR)
    for rank, candidate in reversed(tuple(enumerate(candidates, start=1))):
        point = tuple(int(round(value)) for value in candidate.player_position)
        color = (0, 255, 255) if rank == 1 else (40, 120, 255)
        cv2.circle(canvas, point, 18 if rank == 1 else 12, color, 3)
        cv2.putText(
            canvas,
            str(rank),
            (point[0] + 12, point[1] - 12),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            color,
            2,
            cv2.LINE_AA,
        )
    if canvas.shape[1] > 1200:
        scale = 1200.0 / canvas.shape[1]
        canvas = cv2.resize(
            canvas,
            (1200, int(round(canvas.shape[0] * scale))),
            interpolation=cv2.INTER_AREA,
        )
    return canvas


def _candidate_sheet(images: Sequence[np.ndarray]) -> np.ndarray:
    if not images:
        raise ValueError("candidate sheet requires at least one image")
    cell_width = 320
    cell_height = 260
    cells: list[np.ndarray] = []
    for image in images:
        scale = min(cell_width / image.shape[1], cell_height / image.shape[0])
        resized = cv2.resize(
            image,
            (max(1, int(round(image.shape[1] * scale))), max(1, int(round(image.shape[0] * scale)))),
            interpolation=cv2.INTER_NEAREST,
        )
        cell = np.zeros((cell_height, cell_width, 3), dtype=np.uint8)
        y = (cell_height - resized.shape[0]) // 2
        x = (cell_width - resized.shape[1]) // 2
        cell[y : y + resized.shape[0], x : x + resized.shape[1]] = resized
        cells.append(cell)
    rows: list[np.ndarray] = []
    for start in range(0, len(cells), 2):
        row = cells[start : start + 2]
        if len(row) == 1:
            row.append(np.zeros_like(row[0]))
        rows.append(np.hstack(row))
    return np.vstack(rows)


def _parse_override(value: str) -> tuple[str, Any]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("parameter override must use NAME=JSON_VALUE")
    name, raw_value = value.split("=", 1)
    name = name.strip()
    if not name:
        raise argparse.ArgumentTypeError("parameter name must not be empty")
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        parsed = raw_value
    return name, parsed


def find_latest_readable_sample(root: str | Path) -> Path:
    sample_root = Path(root).expanduser().resolve()
    for candidate in sorted(sample_root.iterdir(), reverse=True):
        try:
            if candidate.is_dir() and (candidate / "sample.json").is_file():
                (candidate / "sample.json").read_bytes()
                return candidate
        except OSError:
            continue
    raise FileNotFoundError(f"no readable capture sample found in {sample_root}")


def run_probe(
    sample_directory: str | Path,
    output_directory: str | Path,
    *,
    config: ProbeConfig | None = None,
    parameter_overrides: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    config = config or ProbeConfig()
    output = Path(output_directory).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    LOGGER.info("step=sample.load path=%s", sample_directory)
    sample = load_sample(sample_directory)
    processed, rebuilt, recognizer_params = rebuild_feature(sample, parameter_overrides)
    cleaned, components = clean_feature_mask(
        rebuilt,
        player_position=sample.player_position,
        player_clear_radius=config.player_clear_radius,
        min_component_area=config.min_component_area,
        min_component_span=config.min_component_span,
    )
    terrain_edge = terrain_edges(sample.terrain, config.terrain_border_clear)
    walkable = terrain_walkable_mask(sample.terrain)
    local_walkable = local_walkable_region(cleaned, sample.player_position)
    LOGGER.info(
        "step=feature.cleaned stored=%s rebuilt=%s cleaned=%s terrain=%s",
        int(np.count_nonzero(sample.stored_feature)),
        int(np.count_nonzero(rebuilt)),
        int(np.count_nonzero(cleaned)),
        int(np.count_nonzero(terrain_edge)),
    )
    candidates = search_candidates(
        cleaned,
        terrain_edge,
        player_position=sample.player_position,
        terrain_walkable=walkable,
        config=config,
    )
    overlays = [
        _candidate_overlay(sample.terrain, cleaned, sample.player_position, candidate)
        for candidate in candidates
    ]
    cv2.imwrite(str(output / "raw.png"), sample.raw)
    cv2.imwrite(str(output / "processed.png"), processed)
    cv2.imwrite(str(output / "stored_feature.png"), sample.stored_feature)
    cv2.imwrite(str(output / "rebuilt_feature.png"), rebuilt)
    cv2.imwrite(str(output / "cleaned_feature.png"), cleaned)
    cv2.imwrite(str(output / "local_walkable.png"), local_walkable)
    cv2.imwrite(str(output / "terrain_edges.png"), terrain_edge)
    cv2.imwrite(str(output / "terrain_walkable.png"), walkable)
    for index, overlay in enumerate(overlays, start=1):
        cv2.imwrite(str(output / f"candidate_{index:02d}_overlay.png"), overlay)
    if overlays:
        cv2.imwrite(str(output / "candidates_sheet.png"), _candidate_sheet(overlays))
        cv2.imwrite(str(output / "candidate_map.png"), _candidate_map(sample.terrain, candidates))

    top_score = candidates[0].score if candidates else 0.0
    second_score = candidates[1].score if len(candidates) > 1 else 0.0
    score_margin = top_score - second_score
    decision_reasons: list[str] = []
    if not candidates:
        decision_reasons.append("no_candidate")
    elif top_score < float(config.acceptance_score):
        decision_reasons.append("score_below_threshold")
    if len(candidates) > 1 and score_margin < float(config.acceptance_margin):
        decision_reasons.append("ambiguous_top_candidates")
    accepted = not decision_reasons
    report = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sample": str(sample.directory),
        "output": str(output),
        "map_instance": sample.manifest.get("terrain", {}),
        "player_local_position": list(sample.player_position),
        "recognizer_params": recognizer_params,
        "parameter_overrides": dict(parameter_overrides or {}),
        "probe_config": asdict(config),
        "features": {
            "stored_nonzero": int(np.count_nonzero(sample.stored_feature)),
            "rebuilt_nonzero": int(np.count_nonzero(rebuilt)),
            "stored_rebuilt_equal": bool(np.array_equal(sample.stored_feature, rebuilt)),
            "stored_rebuilt_support_equal": bool(
                np.array_equal(sample.stored_feature > 0, rebuilt > 0)
            ),
            "cleaned_nonzero": int(np.count_nonzero(cleaned)),
            "local_walkable_nonzero": int(np.count_nonzero(local_walkable)),
            "terrain_edge_nonzero": int(np.count_nonzero(terrain_edge)),
            "components": components,
        },
        "result": {
            "candidate_count": len(candidates),
            "top_score": top_score,
            "second_score": second_score,
            "score_margin": score_margin,
            "accepted": accepted,
            "rejection_reasons": decision_reasons,
            "candidates": [candidate.as_dict(rank) for rank, candidate in enumerate(candidates, 1)],
        },
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    LOGGER.info(
        "step=report.saved output=%s candidates=%s top_score=%.4f margin=%.4f",
        output,
        len(candidates),
        top_score,
        score_margin,
    )
    return report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", default="", help="Saved sample directory; defaults to latest readable sample.")
    parser.add_argument("--out", default="", help="Output directory for report and diagnostic images.")
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        dest="overrides",
        metavar="NAME=JSON_VALUE",
        help="Override one HSVRecognizer parameter; may be repeated.",
    )
    parser.add_argument("--log-level", default="INFO", choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, arguments.log_level),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    sample_root = PROJECT_ROOT / "data" / "poe2_live_terrain_test" / "samples"
    sample = Path(arguments.sample).resolve() if arguments.sample else find_latest_readable_sample(sample_root)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output = (
        Path(arguments.out).resolve()
        if arguments.out
        else PROJECT_ROOT
        / "data"
        / "poe2_live_terrain_test"
        / "probe_results"
        / f"{stamp}-{sample.name}"
    )
    overrides = dict(_parse_override(value) for value in arguments.overrides)
    report = run_probe(sample, output, parameter_overrides=overrides)
    print(
        json.dumps(
            {
                "output": report["output"],
                "candidate_count": report["result"]["candidate_count"],
                "top_score": report["result"]["top_score"],
                "score_margin": report["result"]["score_margin"],
                "accepted": report["result"]["accepted"],
                "rejection_reasons": report["result"]["rejection_reasons"],
                "top_candidate": (
                    report["result"]["candidates"][0]
                    if report["result"]["candidates"]
                    else None
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["result"]["candidate_count"] else 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ProbeConfig",
    "ProbeSample",
    "SearchCandidate",
    "clean_feature_mask",
    "find_latest_readable_sample",
    "local_walkable_region",
    "load_sample",
    "rebuild_feature",
    "run_probe",
    "search_candidates",
    "terrain_edges",
    "terrain_walkable_mask",
    "transform_feature",
]

