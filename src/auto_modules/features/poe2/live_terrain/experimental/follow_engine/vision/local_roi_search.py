"""Encoded minimap marker search used by bounded local recovery.

The adapter is deliberately a pure callable.  It decodes one encoded frame,
examines only the ROI around the predicted role, and maps the best marker back
to native coordinates through the transform belonging to that frame.  It
does not decide whether recovery should run and it never emits a stop action.
"""

from __future__ import annotations

import math
import time
from collections.abc import Sequence
from typing import Callable

import numpy as np

from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import SimilarityTransform2D
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.similarity_search import (
    inverse_transform_local_point,
    transform_local_point,
)
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization.models import MarkerColorProfile

from .capture_adapter import CapturedFrame
from .dual_observation_processor import decode_image_payload
from .marker_processor import extract_markers
from .local_roi_matcher import RoiMatch
from ..contracts import VisualObservation


class EncodedMarkerRoiSearch:
    """Search calibrated marker candidates near one predicted native point."""

    def __init__(
        self,
        *,
        marker_profiles: Sequence[MarkerColorProfile] = (),
        transform: SimilarityTransform2D | None = None,
        identity_hint: str | None = None,
        max_candidates: int = 8,
        decode_image: Callable[[bytes], np.ndarray] = decode_image_payload,
    ) -> None:
        if int(max_candidates) < 1:
            raise ValueError("max_candidates must be positive")
        if transform is not None and (not math.isfinite(float(transform.scale)) or abs(float(transform.scale)) <= 1e-9):
            raise ValueError("transform scale must be finite and non-zero")
        self.marker_profiles = tuple(marker_profiles)
        self.transform = transform
        self.identity_hint = None if identity_hint is None else str(identity_hint).strip() or None
        self.max_candidates = int(max_candidates)
        self.decode_image = decode_image
        self._cached_token: tuple[int, int] | None = None
        self._cached_image: np.ndarray | None = None

    def rebind_session(self, *, transform: SimilarityTransform2D | None = None) -> None:
        """Replace the accepted transform and drop any frame cache."""
        if transform is not None and abs(float(transform.scale)) <= 1e-9:
            raise ValueError("transform scale must be finite and non-zero")
        self.transform = transform
        self._cached_token = None
        self._cached_image = None

    def bind_observation(self, observation: VisualObservation) -> None:
        """Use the wall-corrected transform for the next exact-frame search.

        Control calls this only after its generation/sequence gate.  Legacy
        observations without a transform keep the injected session transform.
        """
        if observation.transform is not None:
            self.transform = observation.transform
        # Reset once per observation; radius expansion and the second role
        # still share a decoded image within this frame.
        self._cached_token = None
        self._cached_image = None

    def __call__(
        self,
        frame: object,
        predicted_position: tuple[float, float],
        radius: float,
    ) -> RoiMatch | None:
        started = time.perf_counter()
        point = (float(predicted_position[0]), float(predicted_position[1]))
        radius = float(radius)
        if not all(math.isfinite(value) for value in point) or not math.isfinite(radius) or radius <= 0.0:
            raise ValueError("ROI search point and radius must be finite and positive")
        image = self._image_for(frame)
        height, width = image.shape[:2]
        if self.transform is None:
            center = point
            local_radius = radius
        else:
            center = inverse_transform_local_point(
                (height, width),
                point,
                angle=self.transform.angle_degrees,
                reflect_horizontal=self.transform.reflect_horizontal,
                scale=self.transform.scale,
                translation=self.transform.translation,
            )
            local_radius = radius / max(abs(float(self.transform.scale)), 1e-9)
        if not all(math.isfinite(value) for value in center) or not math.isfinite(local_radius):
            return None
        margin = max((int(profile.max_dimension) for profile in self.marker_profiles), default=14) + 2
        x0 = max(0, int(math.floor(center[0] - local_radius)) - margin)
        y0 = max(0, int(math.floor(center[1] - local_radius)) - margin)
        x1 = min(width, int(math.ceil(center[0] + local_radius)) + margin + 1)
        y1 = min(height, int(math.ceil(center[1] + local_radius)) + margin + 1)
        if x1 <= x0 or y1 <= y0:
            return None
        crop = image[y0:y1, x0:x1]
        marker_result = extract_markers(
            crop,
            int(getattr(frame, "captured_at_ms", 0)),
            profiles=self.marker_profiles or None,
            max_candidates=self.max_candidates,
        )
        matches: list[tuple[float, float, tuple[float, float]]] = []
        for candidate in marker_result.candidates:
            if float(candidate.area) > 48.0:
                continue
            if self.identity_hint is not None and str(candidate.color_features.get("identity_hint") or "") != self.identity_hint:
                continue
            local_point = (float(candidate.local_position[0] + x0), float(candidate.local_position[1] + y0))
            distance = math.dist(center, local_point)
            if distance > local_radius:
                continue
            identity = str(candidate.color_features.get("identity_hint") or "")
            identity_factor = 1.0 if self.identity_hint is None or identity == self.identity_hint else 0.82
            proximity = max(0.0, 1.0 - distance / max(local_radius, 1.0))
            score = max(0.0, min(1.0, float(candidate.confidence) * (0.70 + 0.30 * proximity) * identity_factor))
            native_point = local_point
            if self.transform is not None:
                native_point = transform_local_point(
                    (height, width),
                    local_point,
                    angle=self.transform.angle_degrees,
                    reflect_horizontal=self.transform.reflect_horizontal,
                    scale=self.transform.scale,
                    translation=self.transform.translation,
                )
            matches.append((distance, score, (float(native_point[0]), float(native_point[1]))))
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        if not matches:
            return RoiMatch(False, None, 0.0, radius, "no_marker", elapsed_ms)
        # A single candidate is the strongest visual correction. With several
        # candidates, prediction is the primary discriminator and confidence
        # is only a tie-breaker; selecting the highest-confidence blob alone
        # can jump to the other role or a static minimap marker.
        if len(matches) == 1:
            _distance, score, native_point = matches[0]
        else:
            _distance, score, native_point = min(matches, key=lambda item: (item[0], -item[1]))
        return RoiMatch(True, native_point, score, radius, "marker_match", elapsed_ms)

    def _image_for(self, frame: object) -> np.ndarray:
        payload = frame.payload if isinstance(frame, CapturedFrame) or hasattr(frame, "payload") else frame
        if not isinstance(payload, (bytes, bytearray, memoryview)):
            raise TypeError("local ROI frame must expose encoded payload bytes")
        token = (id(frame), len(payload))
        if self._cached_token != token:
            image = np.asarray(self.decode_image(bytes(payload)))
            if image.ndim != 3 or image.shape[2] < 3 or image.size == 0:
                raise ValueError("decoded local ROI image is invalid")
            self._cached_token = token
            self._cached_image = np.ascontiguousarray(image[:, :, :3])
        return self._cached_image


__all__ = ["EncodedMarkerRoiSearch"]
