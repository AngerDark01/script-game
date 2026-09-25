"""PoE2 adapter for collecting a larger local map with the generic stitcher."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Callable, Mapping

import cv2
import numpy as np

from auto_modules.core.mapping import MapFrameEvidence, MapStitcher

from .capture_samples import CaptureEvidence


@dataclass(frozen=True)
class Poe2StitchingSnapshot:
    state: str
    map_image: np.ndarray | None
    map_origin: tuple[int, int]
    current_position: tuple[int, int] | None
    trajectory: tuple[tuple[int, int], ...]
    statistics: Mapping[str, float | int]
    draw_scale: float
    player_position: tuple[float, float] | None
    capture_size: tuple[int, int] | None


class Poe2StitchingSession:
    """Own one isolated PoE2 local-map collection session."""

    def __init__(
        self,
        *,
        stitcher_params: Mapping[str, Any] | None = None,
        stitcher_factory: Callable[[], Any] | None = None,
    ) -> None:
        self._stitcher_factory = stitcher_factory
        if stitcher_factory is not None and stitcher_params is None:
            self._stitcher = stitcher_factory()
            get_params = getattr(self._stitcher, "get_params", None)
            current = get_params() if callable(get_params) else None
            self._stitcher_params = self._normalize_params(current)
            setter = getattr(self._stitcher, "set_params", None)
            if callable(setter):
                setter(self._stitcher_params)
        else:
            self._stitcher_params = self._normalize_params(stitcher_params)
            self._stitcher = self._new_stitcher()
        self._state = "idle"
        self._trajectory: list[tuple[int, int]] = []
        self._player_position: tuple[float, float] | None = None
        self._capture_size: tuple[int, int] | None = None

    @property
    def state(self) -> str:
        return self._state

    def start(self) -> Poe2StitchingSnapshot:
        self._state = "running"
        return self.snapshot()

    def pause(self) -> Poe2StitchingSnapshot:
        if self._state == "running":
            self._state = "paused"
        return self.snapshot()

    def configure(
        self,
        stitcher_params: Mapping[str, Any],
    ) -> Poe2StitchingSnapshot:
        params = self._normalize_params(stitcher_params)
        if params == self._stitcher_params:
            return self.snapshot()
        if self._state == "running":
            raise RuntimeError("请先暂停绘图，再应用新的拼接参数")
        self._stitcher_params = params
        self._stitcher = self._new_stitcher()
        self._state = "idle"
        self._trajectory.clear()
        self._player_position = None
        self._capture_size = None
        return self.snapshot()

    def reset(self) -> Poe2StitchingSnapshot:
        self._stitcher = self._new_stitcher()
        self._state = "idle"
        self._trajectory.clear()
        self._player_position = None
        self._capture_size = None
        return self.snapshot()

    @staticmethod
    def _normalize_params(params: Mapping[str, Any] | None) -> dict[str, Any]:
        if params is not None and not isinstance(params, Mapping):
            raise TypeError("stitcher_params must be a mapping")
        complete = MapStitcher.default_params(canvas_size=5000, draw_scale=2.0)
        complete.update(dict(params or {}))
        complete["canvas_size"] = int(complete["canvas_size"])
        complete["draw_scale"] = float(complete["draw_scale"])
        complete["wall_close_kernel_size"] = max(
            1,
            int(complete["wall_close_kernel_size"]),
        )
        return complete

    def _new_stitcher(self):
        params = self._stitcher_params
        if self._stitcher_factory is None:
            stitcher = MapStitcher(
                canvas_size=params["canvas_size"],
                draw_scale=params["draw_scale"],
                wall_close_kernel_size=params["wall_close_kernel_size"],
            )
        else:
            stitcher = self._stitcher_factory()
            reinitialize = getattr(stitcher, "reinitialize_canvas", None)
            if callable(reinitialize):
                reinitialize(
                    canvas_size=params["canvas_size"],
                    draw_scale=params["draw_scale"],
                    wall_close_kernel_size=params["wall_close_kernel_size"],
                )
        setter = getattr(stitcher, "set_params", None)
        if callable(setter):
            setter(params)
        return stitcher

    def consume(self, evidence: CaptureEvidence) -> Poe2StitchingSnapshot:
        if not isinstance(evidence, CaptureEvidence):
            raise TypeError("evidence must be CaptureEvidence")
        if self._state != "running":
            return self.snapshot()

        mapped = self._mapping_evidence(evidence)
        before = self._statistics()
        self._stitcher.add_evidence(mapped)
        after = self._statistics()
        if mapped.player_position is None:
            raise RuntimeError("mapping evidence did not resolve a player position")
        self._player_position = (
            float(mapped.player_position[0]),
            float(mapped.player_position[1]),
        )
        self._capture_size = (int(evidence.raw.shape[1]), int(evidence.raw.shape[0]))

        first_frame = int(before.get("total_frames", 0)) == 0 and int(
            after.get("total_frames", 0)
        ) == 1
        successful_match = int(after.get("successful_matches", 0)) > int(
            before.get("successful_matches", 0)
        )
        low_quality = int(after.get("low_quality_skipped", 0)) > int(
            before.get("low_quality_skipped", 0)
        )
        if first_frame or (successful_match and not low_quality):
            raw_position = self._stitcher.get_current_position()
            position = (int(raw_position[0]), int(raw_position[1]))
            if not self._trajectory or position != self._trajectory[-1]:
                self._trajectory.append(position)
        return self.snapshot()

    def snapshot(self) -> Poe2StitchingSnapshot:
        rendered = self._stitcher.get_enhanced_map(margin=80)
        if isinstance(rendered, tuple):
            map_image, origin = rendered
        else:
            map_image, origin = rendered, (0, 0)
        image = np.array(map_image, copy=True, order="C") if map_image is not None else None
        if image is not None:
            image.setflags(write=False)
        current_position: tuple[int, int] | None = None
        if self._trajectory:
            raw_position = self._stitcher.get_current_position()
            current_position = (int(raw_position[0]), int(raw_position[1]))
        return Poe2StitchingSnapshot(
            state=self._state,
            map_image=image,
            map_origin=(int(origin[0]), int(origin[1])),
            current_position=current_position,
            trajectory=tuple(self._trajectory),
            statistics=MappingProxyType(self._statistics()),
            draw_scale=float(self._stitcher.draw_scale),
            player_position=self._player_position,
            capture_size=self._capture_size,
        )

    def _mapping_evidence(self, evidence: CaptureEvidence) -> MapFrameEvidence:
        feature = self._mask(evidence.feature, "feature")
        wall = self._mask(evidence.wall_mask, "wall_mask") if evidence.wall_mask is not None else feature
        fog = (
            self._mask(evidence.fog_mask, "fog_mask")
            if evidence.fog_mask is not None
            else np.zeros_like(feature)
        )
        raw_gray = (
            self._gray(evidence.raw_gray)
            if evidence.raw_gray is not None
            else self._gray(evidence.processed)
        )
        marker = self._player_marker(evidence.monitor_config, evidence.raw.shape)
        return MapFrameEvidence(
            image=evidence.raw,
            match_mask=feature,
            save_mask=wall,
            fog_mask=fog,
            raw_gray=raw_gray,
            player_position=marker,
            metadata={"captured_at": evidence.captured_at, "source": "poe2-stitching-capture"},
        )

    def _statistics(self) -> dict[str, float | int]:
        return {
            str(key): value
            for key, value in dict(self._stitcher.get_statistics()).items()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        }

    @staticmethod
    def _mask(value: Any, name: str) -> np.ndarray:
        mask = np.asarray(value)
        if mask.ndim == 3:
            mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
        if mask.ndim != 2 or mask.size == 0:
            raise ValueError(f"{name} must be a non-empty 2D mask")
        if mask.dtype != np.uint8:
            mask = np.clip(mask, 0, 255).astype(np.uint8)
        return np.array(mask, copy=True, order="C")

    @staticmethod
    def _gray(value: Any) -> np.ndarray:
        image = np.asarray(value)
        if image.ndim == 2:
            return np.array(image, copy=True, dtype=np.uint8)
        if image.ndim == 3:
            return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        raise ValueError("processed image must be a non-empty 2D or 3D image")

    @staticmethod
    def _player_marker(
        config: Mapping[str, Any],
        frame_shape: tuple[int, ...],
    ) -> tuple[float, float]:
        binding = config.get("binding", {}) if isinstance(config, Mapping) else {}
        marker = binding.get("player_marker_position") if isinstance(binding, Mapping) else None
        if isinstance(marker, (list, tuple)) and len(marker) == 2:
            return float(marker[0]), float(marker[1])
        return float(frame_shape[1]) / 2.0, float(frame_shape[0]) / 2.0


__all__ = ["Poe2StitchingSession", "Poe2StitchingSnapshot"]
