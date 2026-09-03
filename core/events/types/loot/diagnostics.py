from __future__ import annotations

import json
import os
import time
from pathlib import Path

import cv2
import numpy as np

from core.events.debug import event_log

from .assets import ROOT
from .config import LootEventConfig
from .detection.images import pad_small_frame, to_bgr, unpad_bbox
from .detection.pipeline import _pad_bboxes, detect_loot_candidates, detect_loot_presence
from .detection.roi import apply_player_center_mask, build_loot_roi_mask
from .detection.templates import prepare_scaled_templates


class LootDiagnosticCapture:
    """Save throttled runtime artifacts for false-positive loot diagnosis."""

    def __init__(self) -> None:
        stamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
        self.output_dir = ROOT / "debug" / "loot_runtime_diagnostics" / f"{stamp}_pid{os.getpid()}"
        self.last_capture_ms = -1
        self.capture_count = 0

    def maybe_capture(
        self,
        *,
        frame: np.ndarray,
        detections,
        config: LootEventConfig,
        templates,
        exclusion_templates,
        seed_bboxes,
        now_ms: int,
    ) -> None:
        if not bool(getattr(config, "diagnostic_capture_enabled", False)):
            return
        if frame is None or not detections:
            return
        max_frames = max(1, int(getattr(config, "diagnostic_capture_max_frames", 50) or 50))
        if self.capture_count >= max_frames:
            return
        interval_ms = max(0, int(getattr(config, "diagnostic_capture_interval_ms", 1000) or 1000))
        if self.last_capture_ms >= 0 and int(now_ms) - self.last_capture_ms < interval_ms:
            return

        try:
            capture_dir = self.output_dir / f"{int(now_ms)}_{self.capture_count + 1:03d}"
            capture_dir.mkdir(parents=True, exist_ok=True)
            bgr = to_bgr(frame)
            seeds = list(seed_bboxes or [])
            stage_dump_enabled = bool(getattr(config, "diagnostic_stage_dump_enabled", False))
            payload = {
                "now_ms": int(now_ms),
                "capture_kind": "light",
                "frame_shape": [int(value) for value in bgr.shape],
                "config": _diagnostic_config(config),
                "detections": [_detection_dict(item) for item in detections],
                "seeds": [_seed_dict(seed) for seed in seeds],
            }
            _write_image(capture_dir / "raw_minimap.png", bgr)
            _write_image(capture_dir / "detection_overlay.png", _draw_detection_overlay(bgr.copy(), detections))
            if seeds:
                _write_image(capture_dir / "seed_overlay.png", _draw_seed_overlay(bgr.copy(), seeds))
            if stage_dump_enabled:
                raw_mask = build_loot_roi_mask(bgr)
                center_mask = apply_player_center_mask(raw_mask, bgr, config, exclusion_templates or [])
                if not seeds:
                    seeds = list(detect_loot_presence(bgr, config, exclusion_templates or []))
                padded_frame, offset = pad_small_frame(bgr, templates)
                candidates = detect_loot_candidates(
                    padded_frame,
                    templates,
                    config,
                    exclusion_templates or [],
                    _pad_bboxes(seeds, offset),
                )
                _write_image(capture_dir / "stage_raw_mask.png", cv2.cvtColor(raw_mask, cv2.COLOR_GRAY2BGR))
                _write_image(capture_dir / "stage_center_mask.png", cv2.cvtColor(center_mask, cv2.COLOR_GRAY2BGR))
                _write_image(capture_dir / "stage_seed_overlay.png", _draw_seed_overlay(bgr.copy(), seeds))
                _write_image(capture_dir / "stage_candidate_overlay.png", _draw_candidate_overlay(bgr.copy(), candidates, offset))
                payload.update(
                    {
                        "capture_kind": "stage_dump",
                        "raw_mask_pixels": int(np.count_nonzero(raw_mask)),
                        "center_mask_pixels": int(np.count_nonzero(center_mask)),
                        "seeds": [_seed_dict(seed) for seed in seeds],
                        "candidate_count": len(candidates),
                        "accepted_count": int(sum(1 for item in candidates if item.accepted)),
                        "candidates": [_candidate_dict(item, offset, bgr.shape) for item in candidates[:30]],
                    }
                )
            _write_json(capture_dir / "diagnostics.json", payload)
            self.last_capture_ms = int(now_ms)
            self.capture_count += 1
            event_log(
                "loot diagnostic capture saved",
                path=str(capture_dir),
                detections=len(detections),
                kind=payload["capture_kind"],
            )
        except Exception as exc:
            event_log("loot diagnostic capture failed", error=str(exc))


def _diagnostic_config(config: LootEventConfig) -> dict:
    keys = [
        "weighted_threshold",
        "collect_threshold",
        "template_weight",
        "shape_weight",
        "color_weight",
        "min_template_score",
        "min_shape_score",
        "min_color_score",
        "presence_confirm_frames",
        "detection_interval_ms",
        "roi_prefilter_enabled",
        "roi_min_area",
        "roi_max_size",
        "roi_expand",
        "player_center_mask_enabled",
        "player_center_mask_overlay_enabled",
        "player_center_mask_radius",
        "max_blobs_per_frame",
        "diagnostic_stage_dump_enabled",
    ]
    return {key: getattr(config, key, None) for key in keys}


def _detection_dict(detection) -> dict:
    return {
        "event_type": str(getattr(detection, "event_type", "")),
        "confidence": float(getattr(detection, "confidence", 0.0) or 0.0),
        "local_minimap_pos": list(getattr(detection, "local_minimap_pos", ()) or ()),
        "source": str(getattr(detection, "source", "")),
        "metadata": dict(getattr(detection, "metadata", {}) or {}),
    }


def _seed_dict(seed) -> dict:
    x, y, width, height = [int(value) for value in seed]
    return {
        "bbox": [x, y, width, height],
        "center": [int(x + width / 2), int(y + height / 2)],
    }


def _candidate_dict(candidate, offset: tuple[int, int], shape) -> dict:
    bbox = unpad_bbox(
        (
            int(candidate.top_left[0]),
            int(candidate.top_left[1]),
            int(candidate.size[0]),
            int(candidate.size[1]),
        ),
        offset,
        shape,
    )
    center = (
        max(0, min(int(shape[1]) - 1, int(candidate.center[0]) - int(offset[0]))),
        max(0, min(int(shape[0]) - 1, int(candidate.center[1]) - int(offset[1]))),
    )
    return {
        "score": round(float(candidate.score), 4),
        "template_score": round(float(candidate.template_score), 4),
        "shape_score": round(float(candidate.shape_score), 4),
        "color_score": round(float(candidate.color_score), 4),
        "scale": round(float(candidate.scale), 4),
        "accepted": bool(candidate.accepted),
        "template": str(candidate.template_name),
        "color_pixels": int(candidate.color_pixels),
        "bbox": [int(value) for value in bbox],
        "center": [int(center[0]), int(center[1])],
    }


def _draw_seed_overlay(frame: np.ndarray, seeds) -> np.ndarray:
    for index, (x, y, width, height) in enumerate(seeds):
        cv2.rectangle(frame, (int(x), int(y)), (int(x + width), int(y + height)), (0, 255, 255), 1)
        cv2.putText(
            frame,
            f"seed {index}",
            (int(x), max(10, int(y) - 3)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.35,
            (0, 255, 255),
            1,
            cv2.LINE_AA,
        )
    return frame


def _draw_detection_overlay(frame: np.ndarray, detections) -> np.ndarray:
    for index, detection in enumerate(detections):
        metadata = dict(getattr(detection, "metadata", {}) or {})
        bbox = metadata.get("bbox")
        center = getattr(detection, "local_minimap_pos", None)
        if bbox and len(bbox) >= 4:
            x, y, width, height = [int(value) for value in bbox[:4]]
            cv2.rectangle(frame, (x, y), (x + width, y + height), (0, 0, 255), 1)
        if center and len(center) >= 2:
            cx, cy = int(center[0]), int(center[1])
            cv2.drawMarker(frame, (cx, cy), (0, 0, 255), cv2.MARKER_CROSS, 10, 1)
            pickup_radius = metadata.get("pickup_radius")
            if pickup_radius is not None:
                cv2.circle(frame, (cx, cy), max(1, int(pickup_radius)), (0, 120, 255), 1)
            label = f"loot {index} {float(getattr(detection, 'confidence', 0.0) or 0.0):.2f}"
            cv2.putText(
                frame,
                label,
                (max(0, cx - 18), max(10, cy - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.35,
                (0, 0, 255),
                1,
                cv2.LINE_AA,
            )
    return frame


def _draw_candidate_overlay(frame: np.ndarray, candidates, offset: tuple[int, int]) -> np.ndarray:
    for candidate in candidates[:30]:
        x = int(candidate.top_left[0]) - int(offset[0])
        y = int(candidate.top_left[1]) - int(offset[1])
        width, height = candidate.size
        if x >= frame.shape[1] or y >= frame.shape[0] or x + width <= 0 or y + height <= 0:
            continue
        color = (0, 0, 255) if candidate.accepted else (0, 165, 255)
        cv2.rectangle(frame, (x, y), (x + int(width), y + int(height)), color, 1)
        cv2.putText(
            frame,
            f"{candidate.score:.2f}/{candidate.template_score:.2f}/{candidate.shape_score:.2f}/{candidate.color_score:.2f}",
            (x, max(10, y - 3)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.32,
            color,
            1,
            cv2.LINE_AA,
        )
    return frame


def _write_image(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, data = cv2.imencode(path.suffix or ".png", image)
    if ok:
        data.tofile(str(path))


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
