"""Small on-transition evidence bundles for PoE2 marker occlusions."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np

from .models import MarkerColorProfile, PlayerMarkerCandidate


def save_dual_occlusion_evidence(
    root: str | Path,
    *,
    raw: np.ndarray,
    profiles: Sequence[MarkerColorProfile],
    candidates: Sequence[PlayerMarkerCandidate],
    frame_id: int,
    captured_at_ms: int,
    status: str,
    reason: str,
    diagnostics: Mapping,
) -> Path:
    image = np.asarray(raw)
    if image.ndim != 3 or image.shape[2] < 3 or image.size == 0:
        raise ValueError("raw minimap must be a BGR image")
    folder = Path(root) / "occlusion_diagnostics" / f"{captured_at_ms}-{frame_id}-{uuid4().hex[:8]}"
    folder.mkdir(parents=True, exist_ok=False)
    _write_png(folder / "raw.png", image[:, :, :3])
    hsv = cv2.cvtColor(image[:, :, :3], cv2.COLOR_BGR2HSV)
    if profiles:
        for index, profile in enumerate(profiles):
            if profile.hue_min <= profile.hue_max:
                mask = cv2.inRange(
                    hsv,
                    np.array([profile.hue_min, profile.saturation_min, profile.value_min], dtype=np.uint8),
                    np.array([profile.hue_max, 255, 255], dtype=np.uint8),
                )
            else:
                low = cv2.inRange(
                    hsv, np.array([0, profile.saturation_min, profile.value_min], dtype=np.uint8),
                    np.array([profile.hue_max, 255, 255], dtype=np.uint8),
                )
                high = cv2.inRange(
                    hsv, np.array([profile.hue_min, profile.saturation_min, profile.value_min], dtype=np.uint8),
                    np.array([179, 255, 255], dtype=np.uint8),
                )
                mask = cv2.bitwise_or(low, high)
            _write_png(folder / f"mask_{index}.png", mask)
    else:
        _write_png(folder / "mask_saturated.png", cv2.inRange(hsv, (0, 150, 150), (179, 255, 255)))
    payload = {
        "frame_id": int(frame_id),
        "captured_at_ms": int(captured_at_ms),
        "status": status,
        "reason": reason,
        "profiles": [profile.to_dict() for profile in profiles],
        "candidates": [
            {
                "id": item.candidate_id,
                "position": item.local_position,
                "confidence": item.confidence,
                "area": item.area,
                "bbox": item.bbox,
                "color_features": dict(item.color_features),
            }
            for item in candidates
        ],
        "diagnostics": dict(diagnostics),
    }
    (folder / "evidence.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=_json_value),
        encoding="utf-8",
    )
    return folder


def _write_png(path: Path, image: np.ndarray) -> None:
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError(f"cannot encode diagnostic image: {path.name}")
    encoded.tofile(str(path))


def _json_value(value):
    if isinstance(value, np.generic):
        return value.item()
    return str(value)


__all__ = ["save_dual_occlusion_evidence"]
