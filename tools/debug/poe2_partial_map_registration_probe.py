from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, replace
import heapq
import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Any
import uuid

import cv2
import numpy as np


@dataclass(frozen=True)
class HoughConfig:
    min_angle: float = 0.0
    max_angle: float = 360.0
    angle_step: float = 5.0
    min_scale: float = 0.10
    max_scale: float = 0.50
    scale_step: float = 0.02
    min_distance: float = 24.0
    position_threshold: int = 8
    angle_threshold: int = 20
    scale_threshold: int = 10


@dataclass(frozen=True)
class RegistrationConfig:
    hough: HoughConfig = HoughConfig()
    trim_fraction: float = 0.20
    distance_tolerance: float = 3.0
    max_candidates: int = 24
    min_skeleton_pixels: int = 80
    candidate_downsample: float = 0.25
    candidate_line_width: int = 5
    peaks_per_transform: int = 2
    minimum_score: float = 0.68
    minimum_margin: float = 0.05

    def __post_init__(self) -> None:
        if not 0.0 <= self.trim_fraction < 0.5:
            raise ValueError("trim_fraction must be in [0, 0.5)")
        if self.distance_tolerance <= 0.0:
            raise ValueError("distance_tolerance must be positive")
        if not 0.0 < self.candidate_downsample <= 1.0:
            raise ValueError("candidate_downsample must be in (0, 1]")
        if self.candidate_line_width < 1:
            raise ValueError("candidate_line_width must be positive")
        if self.peaks_per_transform < 1:
            raise ValueError("peaks_per_transform must be positive")
        if not 0.0 <= self.minimum_score <= 1.0:
            raise ValueError("minimum_score must be in [0, 1]")
        if self.minimum_margin < 0.0:
            raise ValueError("minimum_margin must not be negative")


@dataclass(frozen=True)
class RegistrationCandidate:
    center: tuple[float, float]
    angle: float
    scale: float
    reflected: bool
    hough_votes: tuple[int, int, int]
    score: float = 0.0
    forward_coverage: float = 0.0
    reverse_coverage: float = 0.0
    forward_distance: float = float("inf")
    reverse_distance: float = float("inf")
    proposal_score: float = 0.0
    source: str = "hough"

    def as_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["center"] = list(self.center)
        result["hough_votes"] = list(self.hough_votes)
        for key in ("score", "forward_coverage", "reverse_coverage", "forward_distance", "reverse_distance"):
            if not np.isfinite(result[key]):
                result[key] = None
        return result


def binary_mask(image: np.ndarray) -> np.ndarray:
    array = np.asarray(image)
    if array.ndim == 3:
        array = cv2.cvtColor(array, cv2.COLOR_BGR2GRAY)
    if array.ndim != 2 or array.size == 0:
        raise ValueError("shape image must be a non-empty 2D array")
    if array.dtype != np.uint8:
        array = cv2.normalize(array, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    _threshold, mask = cv2.threshold(array, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    return mask


def morphological_skeleton(mask: np.ndarray) -> np.ndarray:
    work = binary_mask(mask)
    skeleton = np.zeros_like(work)
    element = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
    while cv2.countNonZero(work):
        eroded = cv2.erode(work, element)
        opened = cv2.dilate(eroded, element)
        skeleton = cv2.bitwise_or(skeleton, cv2.subtract(work, opened))
        work = eroded
    return skeleton


def normalize_shape(image: np.ndarray, *, min_component_area: int = 8) -> np.ndarray:
    mask = binary_mask(image)
    connectivity = cv2.dilate(
        mask,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
    )
    count, labels, _stats, _centroids = cv2.connectedComponentsWithStats(connectivity, 8)
    cleaned = np.zeros_like(mask)
    for label in range(1, count):
        original_pixels = (labels == label) & (mask > 0)
        if int(np.count_nonzero(original_pixels)) >= int(min_component_area):
            cleaned[original_pixels] = 255
    return morphological_skeleton(cleaned)


def project_point(
    point: tuple[float, float],
    *,
    local_center: tuple[float, float],
    global_center: tuple[float, float],
    angle: float,
    scale: float,
    reflected: bool,
) -> tuple[float, float]:
    x = float(point[0]) - float(local_center[0])
    y = float(point[1]) - float(local_center[1])
    if reflected:
        x = -x
    radians = np.deg2rad(float(angle))
    cosine, sine = float(np.cos(radians)), float(np.sin(radians))
    return (
        float(global_center[0]) + scale * (cosine * x - sine * y),
        float(global_center[1]) + scale * (sine * x + cosine * y),
    )


def generate_hough_candidates(
    local_shape: np.ndarray,
    terrain_shape: np.ndarray,
    *,
    config: HoughConfig,
    reflected: bool,
) -> list[RegistrationCandidate]:
    template = binary_mask(local_shape)
    target = binary_mask(terrain_shape)
    if reflected:
        template = cv2.flip(template, 1)

    detector = cv2.createGeneralizedHoughGuil()
    detector.setMinDist(float(config.min_distance))
    detector.setMinAngle(float(config.min_angle))
    detector.setMaxAngle(float(config.max_angle))
    detector.setAngleStep(float(config.angle_step))
    detector.setMinScale(float(config.min_scale))
    detector.setMaxScale(float(config.max_scale))
    detector.setScaleStep(float(config.scale_step))
    detector.setPosThresh(int(config.position_threshold))
    detector.setAngleThresh(int(config.angle_threshold))
    detector.setScaleThresh(int(config.scale_threshold))
    detector.setTemplate(template)
    positions, votes = detector.detect(target)
    if positions is None or votes is None:
        return []

    result: list[RegistrationCandidate] = []
    for position, vote in zip(positions[0], votes[0]):
        x, y, scale, angle = position
        result.append(
            RegistrationCandidate(
                center=(float(x), float(y)),
                angle=float(angle) % 360.0,
                scale=float(scale),
                reflected=reflected,
                hough_votes=tuple(int(value) for value in vote),
            )
        )
    return result


def _float_range(start: float, stop: float, step: float, *, inclusive: bool) -> list[float]:
    if step <= 0.0:
        raise ValueError("search step must be positive")
    if stop < start:
        raise ValueError("search stop must not be less than start")
    epsilon = step * 1e-6
    limit = stop + epsilon if inclusive else stop - epsilon
    count = max(0, int(np.floor((limit - start) / step)) + 1)
    return [float(start + index * step) for index in range(count)]


def _tight_similarity_warp(
    shape: np.ndarray,
    *,
    angle: float,
    scale: float,
) -> tuple[np.ndarray, tuple[float, float]]:
    source = _prepare_for_scaled_warp(shape, scale)
    height, width = source.shape
    center = ((width - 1) / 2.0, (height - 1) / 2.0)
    matrix = cv2.getRotationMatrix2D(center, -float(angle), float(scale))
    corners = np.array(
        [[[0.0, 0.0], [width - 1.0, 0.0], [width - 1.0, height - 1.0], [0.0, height - 1.0]]],
        dtype=np.float32,
    )
    transformed = cv2.transform(corners, matrix)[0]
    lower = np.floor(np.min(transformed, axis=0) - 2.0)
    upper = np.ceil(np.max(transformed, axis=0) + 2.0)
    matrix[:, 2] -= lower
    output_size = (int(upper[0] - lower[0] + 1), int(upper[1] - lower[1] + 1))
    warped_gray = cv2.warpAffine(source, matrix, output_size, flags=cv2.INTER_AREA)
    warped = np.where(warped_gray > 16, 255, 0).astype(np.uint8)
    warped_center = cv2.transform(
        np.array([[[center[0], center[1]]]], dtype=np.float32),
        matrix,
    )[0, 0]
    return warped, (float(warped_center[0]), float(warped_center[1]))


def _prepare_for_scaled_warp(shape: np.ndarray, scale: float) -> np.ndarray:
    source = binary_mask(shape)
    if scale >= 1.0:
        return source
    width = max(1, int(np.ceil(1.0 / max(float(scale), 1e-6))))
    if width % 2 == 0:
        width += 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (width, width))
    return cv2.dilate(source, kernel)


def _standard_width(shape: np.ndarray, line_width: int) -> np.ndarray:
    mask = binary_mask(shape)
    if line_width <= 1:
        return mask
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (line_width, line_width))
    return cv2.dilate(mask, kernel)


def _top_response_locations(
    response: np.ndarray,
    *,
    count: int,
    suppression_radius: int,
) -> list[tuple[float, tuple[int, int]]]:
    work = np.asarray(response, dtype=np.float32).copy()
    result: list[tuple[float, tuple[int, int]]] = []
    for _index in range(count):
        _minimum, maximum, _minimum_location, maximum_location = cv2.minMaxLoc(work)
        if not np.isfinite(maximum):
            break
        result.append((float(maximum), maximum_location))
        x, y = maximum_location
        work[
            max(0, y - suppression_radius) : min(work.shape[0], y + suppression_radius + 1),
            max(0, x - suppression_radius) : min(work.shape[1], x + suppression_radius + 1),
        ] = -np.inf
    return result


def generate_overlap_candidates(
    local_shape: np.ndarray,
    terrain_shape: np.ndarray,
    *,
    config: HoughConfig,
    reflected: bool,
    downsample: float = 0.50,
    line_width: int = 5,
    peaks_per_transform: int = 2,
    max_candidates: int = 24,
) -> list[RegistrationCandidate]:
    if not 0.0 < downsample <= 1.0:
        raise ValueError("downsample must be in (0, 1]")
    if max_candidates < 1:
        return []

    template = binary_mask(local_shape)
    if reflected:
        template = cv2.flip(template, 1)
    target = _standard_width(terrain_shape, line_width)
    if downsample != 1.0:
        target = cv2.resize(target, None, fx=downsample, fy=downsample, interpolation=cv2.INTER_AREA)
    target_float = np.where(target > 0, 1.0, 0.0).astype(np.float32)

    heap: list[tuple[float, int, RegistrationCandidate]] = []
    scale_best: dict[float, tuple[float, int, RegistrationCandidate]] = {}
    sequence = 0
    angles = _float_range(config.min_angle, config.max_angle, config.angle_step, inclusive=False)
    scales = _float_range(config.min_scale, config.max_scale, config.scale_step, inclusive=True)
    for angle in angles:
        for scale in scales:
            warped, warped_center = _tight_similarity_warp(template, angle=angle, scale=scale)
            warped = _standard_width(warped, line_width)
            if downsample != 1.0:
                warped = cv2.resize(
                    warped,
                    None,
                    fx=downsample,
                    fy=downsample,
                    interpolation=cv2.INTER_AREA,
                )
            warped_float = np.where(warped > 0, 1.0, 0.0).astype(np.float32)
            pixel_count = int(np.count_nonzero(warped_float))
            if (
                pixel_count == 0
                or warped_float.shape[0] > target_float.shape[0]
                or warped_float.shape[1] > target_float.shape[1]
            ):
                continue
            response = cv2.matchTemplate(target_float, warped_float, cv2.TM_CCORR_NORMED)
            suppression = max(1, int(round(config.min_distance * downsample)))
            for overlap, location in _top_response_locations(
                response,
                count=peaks_per_transform,
                suppression_radius=suppression,
            ):
                proposal_score = overlap
                center = (
                    (float(location[0]) + warped_center[0] * downsample) / downsample,
                    (float(location[1]) + warped_center[1] * downsample) / downsample,
                )
                candidate = RegistrationCandidate(
                    center=center,
                    angle=angle % 360.0,
                    scale=scale,
                    reflected=reflected,
                    hough_votes=(0, 0, 0),
                    proposal_score=float(proposal_score),
                    source="overlap",
                )
                sequence += 1
                item = (float(proposal_score), sequence, candidate)
                previous_scale_best = scale_best.get(scale)
                if previous_scale_best is None or item[:2] > previous_scale_best[:2]:
                    scale_best[scale] = item
                if len(heap) < max_candidates:
                    heapq.heappush(heap, item)
                elif item[:2] > heap[0][:2]:
                    heapq.heapreplace(heap, item)

    prioritized = sorted(scale_best.values(), reverse=True)
    selected_sequences = {item[1] for item in prioritized}
    prioritized.extend(
        item for item in sorted(heap, reverse=True) if item[1] not in selected_sequences
    )
    ordered = [item[2] for item in prioritized]
    result: list[RegistrationCandidate] = []
    for candidate in ordered:
        if any(
            np.hypot(candidate.center[0] - kept.center[0], candidate.center[1] - kept.center[1])
            < config.min_distance
            and abs(((candidate.angle - kept.angle + 180.0) % 360.0) - 180.0) < config.angle_step
            and abs(candidate.scale - kept.scale) < config.scale_step
            for kept in result
        ):
            continue
        result.append(candidate)
        if len(result) >= max_candidates:
            break
    return result


def trimmed_mean(values: np.ndarray, trim_fraction: float) -> float:
    ordered = np.sort(np.asarray(values, dtype=np.float32).reshape(-1))
    if ordered.size == 0:
        return float("inf")
    keep = max(1, int(round(ordered.size * (1.0 - trim_fraction))))
    return float(np.mean(ordered[:keep]))


def distance_field(shape: np.ndarray) -> np.ndarray:
    return cv2.distanceTransform(
        np.where(binary_mask(shape) > 0, 0, 255).astype(np.uint8),
        cv2.DIST_L2,
        3,
    )


def warp_candidate(
    local_shape: np.ndarray,
    target_shape: tuple[int, int],
    candidate: RegistrationCandidate,
) -> np.ndarray:
    template = cv2.flip(local_shape, 1) if candidate.reflected else local_shape
    template = _prepare_for_scaled_warp(template, candidate.scale)
    center = ((template.shape[1] - 1) / 2.0, (template.shape[0] - 1) / 2.0)
    matrix = cv2.getRotationMatrix2D(center, -candidate.angle, candidate.scale)
    matrix[0, 2] += candidate.center[0] - center[0]
    matrix[1, 2] += candidate.center[1] - center[1]
    warped = cv2.warpAffine(
        template,
        matrix,
        (target_shape[1], target_shape[0]),
        flags=cv2.INTER_AREA,
    )
    return np.where(warped > 16, 255, 0).astype(np.uint8)


def score_candidate(
    local_shape: np.ndarray,
    terrain_shape: np.ndarray,
    candidate: RegistrationCandidate,
    *,
    config: RegistrationConfig,
    terrain_distances: np.ndarray | None = None,
) -> RegistrationCandidate:
    projected = warp_candidate(local_shape, terrain_shape.shape[:2], candidate)
    projected_pixels = projected > 0
    if not np.any(projected_pixels):
        return candidate

    if terrain_distances is None:
        terrain_distances = distance_field(terrain_shape)
    projected_distances = distance_field(projected)
    forward_values = terrain_distances[projected_pixels]

    support_radius = max(2, int(round(config.distance_tolerance * 4.0)))
    y_values, x_values = np.nonzero(projected_pixels)
    x_min = max(0, int(np.min(x_values)) - support_radius)
    x_max = min(projected.shape[1], int(np.max(x_values)) + support_radius + 1)
    y_min = max(0, int(np.min(y_values)) - support_radius)
    y_max = min(projected.shape[0], int(np.max(y_values)) + support_radius + 1)
    support = np.zeros_like(projected_pixels)
    support[y_min:y_max, x_min:x_max] = True
    reverse_pixels = (binary_mask(terrain_shape) > 0) & support
    reverse_values = projected_distances[reverse_pixels]

    forward_distance = trimmed_mean(forward_values, config.trim_fraction)
    reverse_distance = trimmed_mean(reverse_values, config.trim_fraction)
    tolerance = float(config.distance_tolerance)
    forward_coverage = float(np.mean(forward_values <= tolerance))
    reverse_coverage = float(np.mean(reverse_values <= tolerance)) if reverse_values.size else 0.0
    distance_score = float(np.exp(-(forward_distance + reverse_distance) / (2.0 * tolerance)))
    score = 0.40 * forward_coverage + 0.25 * reverse_coverage + 0.35 * distance_score
    return replace(
        candidate,
        score=float(score),
        forward_coverage=forward_coverage,
        reverse_coverage=reverse_coverage,
        forward_distance=forward_distance,
        reverse_distance=reverse_distance,
    )


@dataclass(frozen=True)
class RegistrationResult:
    accepted: bool
    reason: str
    candidates: tuple[RegistrationCandidate, ...]
    score_margin: float


@dataclass(frozen=True)
class ProbeInput:
    session_directory: Path
    stitched_path: Path
    terrain_path: Path
    terrain_source: str
    stitched_sha256: str
    terrain_sha256: str
    stitched_image: np.ndarray
    terrain_image: np.ndarray
    manifest: dict[str, Any]
    local_player: tuple[float, float]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_image(path: Path, *, label: str) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if image is None or image.size == 0:
        raise ValueError(f"{label} is not a readable image: {path}")
    return image


def load_probe_input(
    session_directory: str | Path,
    terrain_input: str | Path | None = None,
) -> ProbeInput:
    session = Path(session_directory).resolve()
    stitched_path = session / "stitched_map.png"
    manifest_path = session / "session.json"
    if not stitched_path.is_file():
        raise FileNotFoundError(f"missing stitched map: {stitched_path}")
    if not manifest_path.is_file():
        raise FileNotFoundError(f"missing session manifest: {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if terrain_input is not None:
        terrain_path = Path(terrain_input).resolve()
        terrain_source = "explicit"
    else:
        terrain_path = session / "terrain.png"
        terrain_source = "session"
    if not terrain_path.is_file():
        raise FileNotFoundError(
            "missing terrain image; provide an explicit terrain path instead of borrowing historical data: "
            f"{terrain_path}"
        )

    map_origin = manifest.get("map_origin")
    current_position = manifest.get("current_position")
    if not (
        isinstance(map_origin, list)
        and len(map_origin) == 2
        and isinstance(current_position, list)
        and len(current_position) == 2
    ):
        raise ValueError("session manifest must contain two-element map_origin and current_position")
    local_player = (
        float(current_position[0]) - float(map_origin[0]),
        float(current_position[1]) - float(map_origin[1]),
    )
    return ProbeInput(
        session_directory=session,
        stitched_path=stitched_path,
        terrain_path=terrain_path,
        terrain_source=terrain_source,
        stitched_sha256=_sha256(stitched_path),
        terrain_sha256=_sha256(terrain_path),
        stitched_image=_load_image(stitched_path, label="stitched map"),
        terrain_image=_load_image(terrain_path, label="terrain"),
        manifest=manifest,
        local_player=local_player,
    )


def _candidate_overlay(
    local_shape: np.ndarray,
    terrain_shape: np.ndarray,
    candidate: RegistrationCandidate,
    *,
    local_player: tuple[float, float],
) -> tuple[np.ndarray, tuple[float, float]]:
    projected = warp_candidate(local_shape, terrain_shape.shape[:2], candidate)
    terrain_pixels = terrain_shape > 0
    projected_pixels = projected > 0
    overlay = np.zeros((*terrain_shape.shape[:2], 3), dtype=np.uint8)
    overlay[terrain_pixels] = (255, 0, 0)
    overlay[projected_pixels] = (0, 255, 0)
    overlay[terrain_pixels & projected_pixels] = (0, 255, 255)
    local_center = ((local_shape.shape[1] - 1) / 2.0, (local_shape.shape[0] - 1) / 2.0)
    projected_player = project_point(
        local_player,
        local_center=local_center,
        global_center=candidate.center,
        angle=candidate.angle,
        scale=candidate.scale,
        reflected=candidate.reflected,
    )
    cv2.circle(
        overlay,
        (int(round(projected_player[0])), int(round(projected_player[1]))),
        7,
        (0, 0, 255),
        -1,
        lineType=cv2.LINE_AA,
    )
    return overlay, projected_player


def _candidate_sheet(images: list[np.ndarray]) -> np.ndarray:
    if not images:
        return np.zeros((120, 160, 3), dtype=np.uint8)
    thumbnails: list[np.ndarray] = []
    for image in images:
        scale = min(1.0, 720.0 / image.shape[1], 520.0 / image.shape[0])
        thumbnails.append(
            cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
            if scale < 1.0
            else image.copy()
        )
    cell_height = max(image.shape[0] for image in thumbnails)
    cell_width = max(image.shape[1] for image in thumbnails)
    columns = min(2, len(thumbnails))
    rows = int(np.ceil(len(thumbnails) / columns))
    sheet = np.zeros((rows * cell_height, columns * cell_width, 3), dtype=np.uint8)
    for index, image in enumerate(thumbnails):
        row, column = divmod(index, columns)
        sheet[
            row * cell_height : row * cell_height + image.shape[0],
            column * cell_width : column * cell_width + image.shape[1],
        ] = image
    return sheet


def save_registration_diagnostics(
    probe_input: ProbeInput,
    result: RegistrationResult,
    output_directory: str | Path,
    *,
    config: RegistrationConfig,
) -> Path:
    output = Path(output_directory).resolve()
    if output.exists():
        raise FileExistsError(f"diagnostic output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.parent / f".{output.name}.{uuid.uuid4().hex}.tmp"
    temporary.mkdir()
    try:
        local_shape = normalize_shape(probe_input.stitched_image)
        terrain_shape = normalize_shape(probe_input.terrain_image)
        if not cv2.imwrite(str(temporary / "local_skeleton.png"), local_shape):
            raise OSError("failed to write local_skeleton.png")
        if not cv2.imwrite(str(temporary / "terrain_skeleton.png"), terrain_shape):
            raise OSError("failed to write terrain_skeleton.png")

        candidate_reports: list[dict[str, Any]] = []
        overlays: list[np.ndarray] = []
        local_center = ((local_shape.shape[1] - 1) / 2.0, (local_shape.shape[0] - 1) / 2.0)
        for index, candidate in enumerate(result.candidates, start=1):
            projected_player = project_point(
                probe_input.local_player,
                local_center=local_center,
                global_center=candidate.center,
                angle=candidate.angle,
                scale=candidate.scale,
                reflected=candidate.reflected,
            )
            entry = candidate.as_dict()
            entry["projected_player"] = [float(projected_player[0]), float(projected_player[1])]
            if index <= 6:
                overlay, _overlay_player = _candidate_overlay(
                    local_shape,
                    terrain_shape,
                    candidate,
                    local_player=probe_input.local_player,
                )
                cv2.putText(
                    overlay,
                    f"#{index} angle={candidate.angle:.1f} scale={candidate.scale:.3f} score={candidate.score:.3f}",
                    (16, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 255, 255),
                    2,
                    cv2.LINE_AA,
                )
                filename = f"candidate_{index:02d}_overlay.png"
                if not cv2.imwrite(str(temporary / filename), overlay):
                    raise OSError(f"failed to write {filename}")
                overlays.append(overlay)
                entry["overlay"] = filename
            candidate_reports.append(entry)

        if not overlays:
            blank = np.zeros((*terrain_shape.shape[:2], 3), dtype=np.uint8)
            blank[terrain_shape > 0] = (255, 0, 0)
            overlays.append(blank)
            cv2.imwrite(str(temporary / "candidate_01_overlay.png"), blank)
        if not cv2.imwrite(str(temporary / "candidates_sheet.png"), _candidate_sheet(overlays)):
            raise OSError("failed to write candidates_sheet.png")

        report = {
            "schema_version": 1,
            "accepted": result.accepted,
            "reason": result.reason,
            "score_margin": result.score_margin,
            "input": {
                "session": str(probe_input.session_directory),
                "terrain": str(probe_input.terrain_path),
                "terrain_source": probe_input.terrain_source,
                "stitched_sha256": probe_input.stitched_sha256,
                "terrain_sha256": probe_input.terrain_sha256,
                "local_player": list(probe_input.local_player),
            },
            "normalization": {
                "local_skeleton_pixels": int(cv2.countNonZero(local_shape)),
                "terrain_skeleton_pixels": int(cv2.countNonZero(terrain_shape)),
            },
            "rendered_candidate_count": len(overlays),
            "config": asdict(config),
            "candidates": candidate_reports,
        }
        (temporary / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temporary, output)
        return output
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Match a PoE2 stitched partial map against an explicit full terrain image.",
    )
    parser.add_argument("--session", required=True, type=Path)
    parser.add_argument("--terrain", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--min-angle", type=float, default=0.0)
    parser.add_argument("--max-angle", type=float, default=360.0)
    parser.add_argument("--angle-step", type=float, default=5.0)
    parser.add_argument("--min-scale", type=float, default=0.10)
    parser.add_argument("--max-scale", type=float, default=0.50)
    parser.add_argument("--scale-step", type=float, default=0.02)
    parser.add_argument("--trim-fraction", type=float, default=0.20)
    parser.add_argument("--max-candidates", type=int, default=24)
    parser.add_argument("--candidate-downsample", type=float, default=0.25)
    parser.add_argument("--minimum-score", type=float, default=0.68)
    parser.add_argument("--minimum-margin", type=float, default=0.05)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_argument_parser().parse_args(argv)
    config = RegistrationConfig(
        hough=HoughConfig(
            min_angle=arguments.min_angle,
            max_angle=arguments.max_angle,
            angle_step=arguments.angle_step,
            min_scale=arguments.min_scale,
            max_scale=arguments.max_scale,
            scale_step=arguments.scale_step,
        ),
        trim_fraction=arguments.trim_fraction,
        max_candidates=arguments.max_candidates,
        candidate_downsample=arguments.candidate_downsample,
        minimum_score=arguments.minimum_score,
        minimum_margin=arguments.minimum_margin,
    )
    probe_input = load_probe_input(arguments.session, arguments.terrain)
    result = register_partial_map(
        probe_input.stitched_image,
        probe_input.terrain_image,
        config=config,
    )
    published = save_registration_diagnostics(
        probe_input,
        result,
        arguments.output,
        config=config,
    )
    winner = result.candidates[0].as_dict() if result.candidates else None
    print(
        json.dumps(
            {
                "accepted": result.accepted,
                "reason": result.reason,
                "score_margin": result.score_margin,
                "winner": winner,
                "output": str(published),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def decide_result(
    candidates: list[RegistrationCandidate],
    *,
    minimum_score: float = 0.68,
    minimum_margin: float = 0.05,
    equivalent_center_distance: float = 12.0,
    equivalent_angle_distance: float = 6.0,
    equivalent_scale_distance: float = 0.05,
) -> RegistrationResult:
    ordered = tuple(sorted(candidates, key=lambda item: item.score, reverse=True))
    if not ordered:
        return RegistrationResult(False, "no_match", (), 0.0)
    winner = ordered[0]
    distinct = [
        item
        for item in ordered[1:]
        if item.reflected != winner.reflected
        or np.hypot(item.center[0] - winner.center[0], item.center[1] - winner.center[1])
        >= equivalent_center_distance
        or abs(((item.angle - winner.angle + 180.0) % 360.0) - 180.0)
        >= equivalent_angle_distance
        or abs(item.scale - winner.scale) >= equivalent_scale_distance
    ]
    second = distinct[0].score if distinct else 0.0
    margin = float(ordered[0].score - second)
    if ordered[0].score < minimum_score:
        return RegistrationResult(False, "low_score", ordered, margin)
    if len(ordered) > 1 and margin < minimum_margin:
        return RegistrationResult(False, "ambiguous", ordered, margin)
    return RegistrationResult(True, "accepted", ordered, margin)


def register_partial_map(
    local_image: np.ndarray,
    terrain_image: np.ndarray,
    *,
    config: RegistrationConfig | None = None,
) -> RegistrationResult:
    active_config = config or RegistrationConfig()
    local_shape = normalize_shape(local_image)
    terrain_shape = normalize_shape(terrain_image)
    if cv2.countNonZero(local_shape) < active_config.min_skeleton_pixels:
        return RegistrationResult(False, "insufficient_local_shape", (), 0.0)
    if cv2.countNonZero(terrain_shape) < active_config.min_skeleton_pixels:
        return RegistrationResult(False, "insufficient_terrain_shape", (), 0.0)

    candidates: list[RegistrationCandidate] = []
    for reflected in (False, True):
        candidates.extend(
            generate_overlap_candidates(
                local_shape,
                terrain_shape,
                config=active_config.hough,
                reflected=reflected,
                downsample=active_config.candidate_downsample,
                line_width=active_config.candidate_line_width,
                peaks_per_transform=active_config.peaks_per_transform,
                max_candidates=active_config.max_candidates,
            )
        )
    terrain_distances = distance_field(terrain_shape)
    scored = [
        score_candidate(
            local_shape,
            terrain_shape,
            candidate,
            config=active_config,
            terrain_distances=terrain_distances,
        )
        for candidate in candidates
    ]
    return decide_result(
        scored,
        minimum_score=active_config.minimum_score,
        minimum_margin=active_config.minimum_margin,
    )


__all__ = [
    "HoughConfig",
    "ProbeInput",
    "RegistrationCandidate",
    "RegistrationConfig",
    "RegistrationResult",
    "binary_mask",
    "build_argument_parser",
    "decide_result",
    "distance_field",
    "generate_hough_candidates",
    "generate_overlap_candidates",
    "load_probe_input",
    "main",
    "morphological_skeleton",
    "normalize_shape",
    "project_point",
    "register_partial_map",
    "score_candidate",
    "save_registration_diagnostics",
    "trimmed_mean",
    "warp_candidate",
]


if __name__ == "__main__":
    raise SystemExit(main())
