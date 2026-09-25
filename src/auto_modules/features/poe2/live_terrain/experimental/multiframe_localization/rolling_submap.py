"""Sparse, bounded local wall map reconstructed from retained keyframes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from .models import MultiFrameEvidence


@dataclass(frozen=True)
class SubmapSnapshot:
    wall_mask: np.ndarray
    observed_mask: np.ndarray
    wall_weight: np.ndarray
    observed_weight: np.ndarray
    last_frame_id: np.ndarray
    origin: tuple[int, int]
    frame_ids: tuple[int, ...]

    def __post_init__(self) -> None:
        wall = np.array(self.wall_mask, dtype=np.uint8, copy=True, order="C")
        observed = np.array(self.observed_mask, dtype=np.uint8, copy=True, order="C")
        if wall.ndim != 2 or observed.shape != wall.shape or wall.size == 0:
            raise ValueError("submap masks must be non-empty and have equal shapes")
        wall_weight = np.array(self.wall_weight, dtype=np.float32, copy=True, order="C")
        observed_weight = np.array(self.observed_weight, dtype=np.float32, copy=True, order="C")
        last_frame_id = np.array(self.last_frame_id, dtype=np.int64, copy=True, order="C")
        if wall_weight.shape != wall.shape or observed_weight.shape != wall.shape:
            raise ValueError("submap weights must match mask shape")
        if last_frame_id.shape != wall.shape:
            raise ValueError("last_frame_id must match mask shape")
        wall.setflags(write=False)
        observed.setflags(write=False)
        wall_weight.setflags(write=False)
        observed_weight.setflags(write=False)
        last_frame_id.setflags(write=False)
        object.__setattr__(self, "wall_mask", wall)
        object.__setattr__(self, "observed_mask", observed)
        object.__setattr__(self, "wall_weight", wall_weight)
        object.__setattr__(self, "observed_weight", observed_weight)
        object.__setattr__(self, "last_frame_id", last_frame_id)
        object.__setattr__(self, "origin", (int(self.origin[0]), int(self.origin[1])))
        object.__setattr__(self, "frame_ids", tuple(int(v) for v in self.frame_ids))


class RollingSubmap:
    """Keep only the current evidence window and rebuild it deterministically."""

    def __init__(
        self,
        *,
        max_width: int = 1024,
        max_height: int = 1024,
        min_frame_weight: float = 0.05,
        max_frame_weight: float = 1.0,
        min_support_weight: float = 0.05,
        wall_probability_threshold: float = 0.5,
    ) -> None:
        if max_width < 1 or max_height < 1:
            raise ValueError("submap dimensions must be positive")
        if not 0 < min_frame_weight <= max_frame_weight:
            raise ValueError("frame weight limits are invalid")
        if min_support_weight <= 0 or not 0 <= wall_probability_threshold <= 1:
            raise ValueError("submap support thresholds are invalid")
        self.max_width = int(max_width)
        self.max_height = int(max_height)
        self.min_frame_weight = float(min_frame_weight)
        self.max_frame_weight = float(max_frame_weight)
        self.min_support_weight = float(min_support_weight)
        self.wall_probability_threshold = float(wall_probability_threshold)
        self._snapshot: SubmapSnapshot | None = None

    def rebuild(self, frames: Sequence[MultiFrameEvidence]) -> SubmapSnapshot:
        retained = [item for item in frames if item.is_keyframe]
        if not retained:
            shape = (1, 1)
            self._snapshot = SubmapSnapshot(
                wall_mask=np.zeros(shape, dtype=np.uint8),
                observed_mask=np.zeros(shape, dtype=np.uint8),
                wall_weight=np.zeros(shape, dtype=np.float32),
                observed_weight=np.zeros(shape, dtype=np.float32),
                last_frame_id=np.full(shape, -1, dtype=np.int64),
                origin=(0, 0),
                frame_ids=(),
            )
            return self._snapshot
        boxes = []
        for item in retained:
            h, w = item.frame.wall_mask.shape
            x, y = item.local_offset
            boxes.append((round(x), round(y), round(x) + w, round(y) + h))
        full_min_x = min(box[0] for box in boxes)
        full_min_y = min(box[1] for box in boxes)
        full_max_x = max(box[2] for box in boxes)
        full_max_y = max(box[3] for box in boxes)
        width = min(self.max_width, max(1, full_max_x - full_min_x))
        height = min(self.max_height, max(1, full_max_y - full_min_y))
        latest_box = boxes[-1]
        latest_center_x = (latest_box[0] + latest_box[2]) // 2
        latest_center_y = (latest_box[1] + latest_box[3]) // 2
        min_x = min(max(full_min_x, latest_center_x - width // 2), full_max_x - width)
        min_y = min(max(full_min_y, latest_center_y - height // 2), full_max_y - height)
        wall_weight = np.zeros((height, width), dtype=np.float32)
        observed_weight = np.zeros((height, width), dtype=np.float32)
        last_frame_id = np.full((height, width), -1, dtype=np.int64)
        for item in retained:
            mask = item.frame.wall_mask
            visible = np.asarray(item.observed_mask)
            x = round(item.local_offset[0]) - min_x
            y = round(item.local_offset[1]) - min_y
            src_x0, src_y0 = max(0, -x), max(0, -y)
            dst_x0, dst_y0 = max(0, x), max(0, y)
            copy_w = min(mask.shape[1] - src_x0, width - dst_x0)
            copy_h = min(mask.shape[0] - src_y0, height - dst_y0)
            if copy_w <= 0 or copy_h <= 0:
                continue
            src = mask[src_y0 : src_y0 + copy_h, src_x0 : src_x0 + copy_w]
            visible_src = visible[src_y0 : src_y0 + copy_h, src_x0 : src_x0 + copy_w]
            region = (slice(dst_y0, dst_y0 + copy_h), slice(dst_x0, dst_x0 + copy_w))
            visible_cells = visible_src > 0
            contribution = min(
                self.max_frame_weight,
                max(self.min_frame_weight, float(item.motion.quality)),
            )
            observed_region = observed_weight[region]
            wall_region = wall_weight[region]
            last_region = last_frame_id[region]
            observed_region[visible_cells] += contribution
            wall_region[visible_cells] += contribution * (src[visible_cells] > 0)
            last_region[visible_cells] = item.frame.frame_id
        supported = observed_weight >= self.min_support_weight
        wall_probability = wall_weight / np.maximum(observed_weight, 1e-6)
        wall = np.where(
            supported & (wall_probability >= self.wall_probability_threshold),
            255,
            0,
        ).astype(np.uint8)
        observed = np.where(observed_weight > 0, 255, 0).astype(np.uint8)
        self._snapshot = SubmapSnapshot(
            wall_mask=wall,
            observed_mask=observed,
            wall_weight=wall_weight,
            observed_weight=observed_weight,
            last_frame_id=last_frame_id,
            origin=(min_x, min_y),
            frame_ids=tuple(item.frame.frame_id for item in retained),
        )
        return self._snapshot

    def snapshot(self) -> SubmapSnapshot:
        if self._snapshot is None:
            return self.rebuild(())
        return self._snapshot


__all__ = ["RollingSubmap", "SubmapSnapshot"]
