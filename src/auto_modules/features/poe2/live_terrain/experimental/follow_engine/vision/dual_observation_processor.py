"""Pure composition of one minimap frame into a :class:`VisualObservation`.

The processor deliberately stops at the vision boundary.  It decodes the
frame payload, estimates wall displacement, extracts marker candidates and
associates them with the two seeded roles.  It does not read game memory,
touch Qt, plan a route, or send controller input.  Missing markers therefore
produce a degraded observation rather than a stop signal.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import cv2
import numpy as np

from auto_modules.core.localization import transform_local_displacement
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import (
    SimilarityTransform2D,
)
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.similarity_search import (
    inverse_transform_local_point,
    transform_local_point,
)
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization.models import (
    MarkerColorProfile,
)

from ..contracts import (
    ObservationSource,
    RoleVisualObservation,
    StageTiming,
    VisualObservation,
)
from ..timing import TimingWindow
from .capture_adapter import CapturedFrame
from .dual_association import DualRoleAssociator
from .marker_processor import extract_markers
from .wall_processor import WallObservation, process_wall


ImageDecoder = Callable[[bytes], np.ndarray]
WallExtractor = Callable[[np.ndarray], np.ndarray]


def decode_image_payload(payload: bytes) -> np.ndarray:
    """Decode an encoded BGR image inside the vision process.

    Keeping this operation inside the processor avoids pickling a NumPy array
    through the process boundary.  PNG/JPEG bytes are accepted; malformed or
    empty payloads fail explicitly so the supervisor can report the frame
    error with its generation and sequence.
    """

    if not isinstance(payload, (bytes, bytearray, memoryview)) or not payload:
        raise ValueError("frame payload must contain encoded image bytes")
    encoded = np.frombuffer(bytes(payload), dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if image is None or image.ndim != 3 or image.shape[2] < 3 or image.size == 0:
        raise ValueError("frame payload is not a decodable color image")
    return image[:, :, :3]


def default_wall_extractor(image: np.ndarray) -> np.ndarray:
    """Extract a conservative bright wall mask from a BGR minimap image."""

    array = np.asarray(image)
    if array.ndim != 3 or array.shape[2] < 3 or array.size == 0:
        raise ValueError("wall extractor expects a non-empty BGR image")
    gray = cv2.cvtColor(array[:, :, :3], cv2.COLOR_BGR2GRAY)
    # Wall edges in the existing localization pipeline are represented by the
    # bright part of the terrain.  No dilation is applied here: the tracker
    # must not make narrow passages impassable merely during observation.
    return np.where(gray >= 180, 255, 0).astype(np.uint8)


class DualObservationProcessor:
    """Compose marker and wall processors using a seeded first-frame transform.

    ``initial_positions_native`` are the only absolute role anchors needed by
    this class.  ``initial_screen_positions`` can be supplied when the first
    frame used for registration is available; otherwise the positions are
    inverted through ``transform`` after the first image reveals its shape.
    """

    def __init__(
        self,
        *,
        generation: int,
        map_instance: str,
        role_ids: tuple[str, ...],
        marker_profiles: Sequence[MarkerColorProfile] = (),
        initial_positions_native: Mapping[str, tuple[float, float]],
        initial_screen_positions: Mapping[str, tuple[float, float]] | None = None,
        transform: SimilarityTransform2D | None = None,
        identity_hints: Mapping[str, str] | None = None,
        associator: DualRoleAssociator | None = None,
        max_candidates: int | None = None,
        decode_image: ImageDecoder = decode_image_payload,
        wall_extractor: WallExtractor = default_wall_extractor,
    ) -> None:
        normalized_roles = tuple(str(role).strip() for role in role_ids)
        if not normalized_roles or any(not role for role in normalized_roles):
            raise ValueError("role_ids must contain non-empty role names")
        if len(set(normalized_roles)) != len(normalized_roles):
            raise ValueError("role_ids must be unique")
        if int(generation) <= 0 or not str(map_instance).strip():
            raise ValueError("generation and map_instance are required")
        positions = {str(role): self._point(value, f"initial position {role}") for role, value in initial_positions_native.items()}
        if set(positions) != set(normalized_roles):
            raise ValueError("initial_positions_native must contain exactly role_ids")
        screens = None
        if initial_screen_positions is not None:
            screens = {str(role): self._point(value, f"initial screen position {role}") for role, value in initial_screen_positions.items()}
            if set(screens) != set(normalized_roles):
                raise ValueError("initial_screen_positions must contain exactly role_ids")
        if max_candidates is not None and int(max_candidates) < len(normalized_roles):
            raise ValueError("max_candidates must cover every role")
        self.generation = int(generation)
        self.map_instance = str(map_instance).strip()
        self.role_ids = normalized_roles
        self.marker_profiles = tuple(marker_profiles)
        self.initial_positions_native = positions
        self.transform = transform
        self.identity_hints = {str(key): str(value) for key, value in (identity_hints or {}).items()}
        self.associator = associator or DualRoleAssociator()
        self.max_candidates = int(max_candidates or max(6, len(normalized_roles) * 3))
        self.decode_image = decode_image
        self.wall_extractor = wall_extractor
        self._screen_positions = screens
        self._native_positions = dict(positions)
        self._native_velocities = {role: (0.0, 0.0) for role in normalized_roles}
        self._last_visual_at = {role: None for role in normalized_roles}
        self._last_sequence = -1
        self._last_wall: np.ndarray | None = None
        self._last_wall_shape: tuple[int, int] | None = None
        self._last_timestamp: int | None = None
        self._last_association_diagnostics: dict[str, Any] = {}
        self._processing_timing = TimingWindow(256)
        self._transform = transform

    def rebind_session(self, *, generation: int, map_instance: str) -> None:
        """Reset per-session temporal state when a worker is reused."""

        if int(generation) <= 0 or not str(map_instance).strip():
            raise ValueError("generation and map instance are required")
        self.generation = int(generation)
        self.map_instance = str(map_instance).strip()
        self._native_positions = dict(self.initial_positions_native)
        self._native_velocities = {role: (0.0, 0.0) for role in self.role_ids}
        self._last_visual_at = {role: None for role in self.role_ids}
        self._last_sequence = -1
        self._last_wall = None
        self._last_wall_shape = None
        self._last_timestamp = None
        self._last_association_diagnostics = {}
        self._transform = self.transform

    @staticmethod
    def _point(value: Any, field_name: str) -> tuple[float, float]:
        if not isinstance(value, (tuple, list)) or len(value) != 2:
            raise ValueError(f"{field_name} must contain two values")
        point = (float(value[0]), float(value[1]))
        if not all(math.isfinite(item) for item in point):
            raise ValueError(f"{field_name} must contain finite values")
        return point

    def process(self, frame: CapturedFrame) -> VisualObservation:
        """Process one fresh frame and return a normalized native observation."""

        started = time.perf_counter()
        self._validate_frame(frame)
        decode_started = time.perf_counter()
        image = self.decode_image(frame.payload)
        decode_ms = (time.perf_counter() - decode_started) * 1000.0
        wall_started = time.perf_counter()
        wall = np.asarray(self.wall_extractor(image))
        if wall.ndim != 2 or wall.shape != image.shape[:2] or wall.size == 0:
            raise ValueError("wall extractor must return a non-empty mask matching the image")
        wall = np.where(wall > 0, 255, 0).astype(np.uint8, copy=False)
        wall_ms = (time.perf_counter() - wall_started) * 1000.0
        wall_match_started = time.perf_counter()
        wall_observation = self._wall_observation(wall)
        wall_match_ms = (time.perf_counter() - wall_match_started) * 1000.0
        marker_result = extract_markers(
            image,
            frame.captured_at_ms,
            profiles=self.marker_profiles or None,
            max_candidates=self.max_candidates,
        )
        marker_ms = float(marker_result.processing_ms)

        transform = self._update_transform(wall_observation.shift, wall.shape)
        predicted_screen = self._predicted_screen_positions(wall_observation.shift, wall.shape, transform)
        association_started = time.perf_counter()
        association = self.associator.assign(
            marker_result.candidates,
            predicted_screen,
            identity_hints=self.identity_hints or None,
            velocities=self._screen_velocities_for_association(wall_observation.shift, wall.shape),
            elapsed_ms=self._elapsed_by_role(frame.captured_at_ms),
            wall_shift=wall_observation.shift or (0.0, 0.0),
            captured_at_ms=frame.captured_at_ms,
        )
        self._last_association_diagnostics = dict(association.diagnostics)
        association_ms = (time.perf_counter() - association_started) * 1000.0
        roles, assignment_score = self._build_roles(
            frame.captured_at_ms,
            association.assignments,
            association.diagnostics,
            predicted_screen,
            transform,
            wall.shape,
        )
        self._last_wall = wall.copy()
        self._last_wall_shape = tuple(int(value) for value in wall.shape)
        self._last_sequence = int(frame.sequence)
        self._last_timestamp = int(frame.captured_at_ms)
        visible_count = sum(1 for item in roles.values() if item.visible)
        if visible_count == len(self.role_ids):
            source = ObservationSource.VISUAL
        elif visible_count:
            source = ObservationSource.PARTIAL
        else:
            source = ObservationSource.NONE
        total_ms = (time.perf_counter() - started) * 1000.0
        self._processing_timing.add(total_ms)
        timing = StageTiming(
            capture_ms=decode_ms,
            wall_ms=wall_ms + wall_match_ms,
            marker_ms=marker_ms,
            association_ms=association_ms,
            total_ms=total_ms,
        )
        return VisualObservation(
            generation=self.generation,
            sequence=int(frame.sequence),
            captured_at_ms=int(frame.captured_at_ms),
            map_instance=self.map_instance,
            roles=roles,
            wall_shift=wall_observation.shift,
            wall_quality=float(wall_observation.quality),
            assignment_score=assignment_score,
            association_diagnostics=self._last_association_diagnostics,
            source=source,
            timing=timing,
            # Carry the transform that produced this observation across the
            # worker boundary.  The transform is updated from wall motion on
            # every frame, so a replacement worker must inherit this latest
            # registration rather than falling back to the first-frame seed.
            transform=transform,
        )

    def timing_diagnostics(self) -> dict[str, object]:
        """Return bounded monotonic processing percentiles for diagnostics."""
        return self._processing_timing.as_dict("vision_processing_")

    def _validate_frame(self, frame: CapturedFrame) -> None:
        if not isinstance(frame, CapturedFrame):
            raise TypeError("frame must be CapturedFrame")
        if int(frame.generation) != self.generation or str(frame.map_instance).strip() != self.map_instance:
            raise ValueError("frame belongs to a different generation or map instance")
        if int(frame.sequence) <= self._last_sequence:
            raise ValueError("frame sequence must be strictly increasing")
        if int(frame.captured_at_ms) < 0:
            raise ValueError("captured_at_ms must be non-negative")

    def _wall_observation(self, current: np.ndarray) -> WallObservation:
        if self._last_wall is None:
            return WallObservation(None, 0.0, False, "first_frame")
        return process_wall(self._last_wall, current)

    def _update_transform(
        self,
        wall_shift: tuple[float, float] | None,
        shape: tuple[int, int],
    ) -> SimilarityTransform2D | None:
        transform = self._transform
        if transform is None or wall_shift is None:
            return transform
        delta = transform_local_displacement(
            wall_shift,
            angle_degrees=transform.angle_degrees,
            reflect_horizontal=transform.reflect_horizontal,
            scale=transform.scale,
        )
        updated = SimilarityTransform2D(
            transform.angle_degrees,
            transform.reflect_horizontal,
            transform.scale,
            (transform.translation[0] - delta[0], transform.translation[1] - delta[1]),
        )
        self._transform = updated
        return updated

    def _predicted_screen_positions(
        self,
        wall_shift: tuple[float, float] | None,
        shape: tuple[int, int],
        transform: SimilarityTransform2D | None,
    ) -> dict[str, tuple[float, float]]:
        if self._screen_positions is None:
            if transform is None:
                self._screen_positions = dict(self._native_positions)
            else:
                self._screen_positions = {
                    role: inverse_transform_local_point(
                        shape,
                        position,
                        angle=transform.angle_degrees,
                        reflect_horizontal=transform.reflect_horizontal,
                        scale=transform.scale,
                        translation=transform.translation,
                    )
                    for role, position in self._native_positions.items()
                }
        shift = wall_shift or (0.0, 0.0)
        return {
            role: (point[0] + float(shift[0]), point[1] + float(shift[1]))
            for role, point in self._screen_positions.items()
        }

    def _screen_velocities_for_association(
        self, wall_shift: tuple[float, float] | None, shape: tuple[int, int],
    ) -> dict[str, tuple[float, float]]:
        # Association operates in screen pixels.  Native velocity therefore
        # needs the inverse registration linear map; applying the forward
        # native<-screen transform here magnifies/rotates the prediction twice.
        if self._transform is None:
            return dict(self._native_velocities)
        result: dict[str, tuple[float, float]] = {}
        for role, velocity in self._native_velocities.items():
            origin = inverse_transform_local_point(
                shape, (0.0, 0.0), angle=self._transform.angle_degrees,
                reflect_horizontal=self._transform.reflect_horizontal,
                scale=self._transform.scale, translation=self._transform.translation,
            )
            shifted = inverse_transform_local_point(
                shape, (float(velocity[0]), float(velocity[1])), angle=self._transform.angle_degrees,
                reflect_horizontal=self._transform.reflect_horizontal,
                scale=self._transform.scale, translation=self._transform.translation,
            )
            result[role] = (shifted[0] - origin[0], shifted[1] - origin[1])
        return result

    def _elapsed_by_role(self, timestamp: int) -> dict[str, int]:
        return {
            role: 0 if last is None else max(0, int(timestamp) - int(last))
            for role, last in self._last_visual_at.items()
        }

    def _build_roles(
        self,
        timestamp: int,
        assignments: Mapping[str, tuple[float, float]],
        diagnostics: Mapping[str, Any],
        predicted_screen: Mapping[str, tuple[float, float]],
        transform: SimilarityTransform2D | None,
        shape: tuple[int, int],
    ) -> tuple[dict[str, RoleVisualObservation], float]:
        gates = diagnostics.get("gates", {}) if isinstance(diagnostics, Mapping) else {}
        role_observations: dict[str, RoleVisualObservation] = {}
        visible_distances: list[float] = []
        for role in self.role_ids:
            screen_point = assignments.get(role)
            if screen_point is not None:
                if transform is None:
                    native_point = (float(screen_point[0]), float(screen_point[1]))
                else:
                    native_point = transform_local_point(
                        shape,
                        screen_point,
                        angle=transform.angle_degrees,
                        reflect_horizontal=transform.reflect_horizontal,
                        scale=transform.scale,
                        translation=transform.translation,
                    )
                previous = self._native_positions[role]
                # A role may be occluded for several frames while the other
                # role remains visible.  Its velocity must use the role's
                # last accepted timestamp, not the global previous frame;
                # otherwise the first reappearing sample is divided by a
                # tiny frame interval and the association gate jumps away.
                previous_timestamp = self._last_visual_at.get(role)
                elapsed_ms = max(1, 0 if previous_timestamp is None else timestamp - int(previous_timestamp))
                dt = elapsed_ms / 1000.0
                velocity = ((native_point[0] - previous[0]) / dt, (native_point[1] - previous[1]) / dt)
                confirmed = role in diagnostics.get("confirmed_roles", ())
                if confirmed:
                    # Correcting an anchor is not measured physical velocity.
                    velocity = (0.0, 0.0)
                self._native_positions[role] = native_point
                self._native_velocities[role] = velocity
                self._screen_positions[role] = (float(screen_point[0]), float(screen_point[1]))
                self._last_visual_at[role] = int(timestamp)
                distance = math.dist(predicted_screen[role], screen_point)
                visible_distances.append(distance)
                gate = max(1.0, float(gates.get(role, 45.0)))
                confidence = max(0.0, min(1.0, 1.0 - distance / gate))
                if confirmed:
                    confidence = 0.9
                role_observations[role] = RoleVisualObservation(
                    role_id=role,
                    position_native=native_point,
                    velocity_native=velocity,
                    confidence=confidence,
                    uncertainty_native=2.0 if confirmed else max(1.0, distance),
                    visible=True,
                    last_visual_at_ms=int(timestamp),
                    association_cost=distance,
                )
            else:
                age = 0.0 if self._last_visual_at[role] is None else max(0, timestamp - int(self._last_visual_at[role]))
                uncertainty = min(1000.0, 8.0 + age * 0.02)
                role_observations[role] = RoleVisualObservation(
                    role_id=role,
                    position_native=self._native_positions[role],
                    velocity_native=self._native_velocities[role],
                    confidence=0.0,
                    uncertainty_native=uncertainty,
                    visible=False,
                    last_visual_at_ms=self._last_visual_at[role],
                    association_cost=0.0,
                )
        if not assignments:
            score = 0.0
        else:
            score = len(assignments) / len(self.role_ids)
            if visible_distances:
                mean_gate = sum(max(1.0, float(gates.get(role, 45.0))) for role in assignments) / len(assignments)
                score *= max(0.0, min(1.0, 1.0 - (sum(visible_distances) / len(visible_distances)) / mean_gate))
        return role_observations, float(score)


__all__ = ["DualObservationProcessor", "decode_image_payload", "default_wall_extractor"]
