from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass(frozen=True)
class MinimapSampleCaptureResult:
    ok: bool
    message: str
    image_path: str = ""
    metadata_path: str = ""


def save_minimap_sample(
    *,
    project_root: str | Path,
    map_name: str,
    frame,
    capture_rect: dict | None,
    monitor_size: int | None,
    player_local_pos,
    source: str,
    now_ms: int | None = None,
) -> MinimapSampleCaptureResult:
    """Persist one minimap frame plus metadata for detector samples."""
    if frame is None:
        return MinimapSampleCaptureResult(False, "没有可保存的小地图截图。")

    bgr = _to_bgr(frame)
    if bgr is None or bgr.size == 0:
        return MinimapSampleCaptureResult(False, "小地图截图为空。")

    timestamp_ms = int(now_ms if now_ms is not None else time.time() * 1000)
    stamp = time.strftime("%Y%m%d_%H%M%S", time.localtime(timestamp_ms / 1000))
    suffix_ms = timestamp_ms % 1000
    safe_map_name = _safe_name(map_name or "unknown_map")
    sample_dir = Path(project_root) / "debug" / "minimap_samples" / safe_map_name
    sample_dir.mkdir(parents=True, exist_ok=True)

    stem = f"{stamp}_{suffix_ms:03d}_{safe_map_name}_minimap"
    image_path = sample_dir / f"{stem}.png"
    metadata_path = sample_dir / f"{stem}.json"

    if not _write_image(image_path, bgr):
        return MinimapSampleCaptureResult(False, f"保存截图失败: {image_path}")

    metadata = {
        "saved_at_ms": timestamp_ms,
        "map_name": map_name or "",
        "source": str(source or ""),
        "image": str(image_path),
        "capture_rect": dict(capture_rect or {}),
        "monitor_size": int(monitor_size or 0),
        "player_local_pos": _point_list(player_local_pos),
        "frame_shape": [int(value) for value in bgr.shape],
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return MinimapSampleCaptureResult(
        True,
        f"已保存小地图样本: {image_path}",
        image_path=str(image_path),
        metadata_path=str(metadata_path),
    )


def capture_current_minimap_frame(*, build_capture_geometry, screen_capture):
    """Capture one frame using the current navigation monitor geometry."""
    capture_rect, player_pos = build_capture_geometry()
    if not capture_rect:
        return None, None, None
    frame = screen_capture.capture(
        capture_rect["left"],
        capture_rect["top"],
        capture_rect["width"],
        capture_rect["height"],
    )
    return frame, capture_rect, player_pos


def _to_bgr(frame):
    image = np.asarray(frame)
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.ndim == 3 and image.shape[2] == 4:
        return image[:, :, :3].copy()
    if image.ndim == 3 and image.shape[2] >= 3:
        return image[:, :, :3].copy()
    return None


def _write_image(path: Path, image: np.ndarray) -> bool:
    ok, encoded = cv2.imencode(path.suffix or ".png", image)
    if not ok:
        return False
    encoded.tofile(str(path))
    return True


def _safe_name(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in str(value).strip())
    return cleaned.strip("_") or "unknown_map"


def _point_list(point) -> list[int] | None:
    if point is None:
        return None
    try:
        return [int(point[0]), int(point[1])]
    except (TypeError, ValueError, IndexError):
        return None
