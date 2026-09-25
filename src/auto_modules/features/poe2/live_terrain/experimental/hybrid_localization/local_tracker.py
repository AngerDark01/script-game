"""Bounded visual tracking with a fixed confirmed similarity transform."""

from __future__ import annotations

import math
from typing import Any

from auto_modules.core.localization import (
    LocalizationResult,
    canonical_wall_mask,
    estimate_bounded_displacement,
    transform_local_displacement,
)

from .models import AbsoluteRegistration, HybridFrame, SimilarityTransform2D
from .similarity_search import transform_feature


class VisualLocalTracker:
    def __init__(
        self,
        matcher: Any,
        *,
        search_radius: float = 96.0,
        displacement_min_quality: float = 0.20,
        displacement_max_shift: float = 40.0,
        max_global_jump: float = 120.0,
        correction_frame_interval: int = 0,
        correction_distance: float = 0.0,
        correction_interval_ms: int = 0,
    ) -> None:
        radius = float(search_radius)
        min_quality = float(displacement_min_quality)
        max_shift = float(displacement_max_shift)
        max_jump = float(max_global_jump)
        frame_interval = int(correction_frame_interval)
        distance_interval = float(correction_distance)
        time_interval = int(correction_interval_ms)
        if not math.isfinite(radius) or radius < 0:
            raise ValueError("search_radius must be finite and non-negative")
        if not math.isfinite(min_quality) or not 0.0 <= min_quality <= 1.0:
            raise ValueError("displacement_min_quality must be between zero and one")
        if not math.isfinite(max_shift) or max_shift <= 0:
            raise ValueError("displacement_max_shift must be positive")
        if not math.isfinite(max_jump) or max_jump <= 0:
            raise ValueError("max_global_jump must be positive")
        if frame_interval < 0 or not math.isfinite(distance_interval) or distance_interval < 0 or time_interval < 0:
            raise ValueError("correction intervals must be non-negative")
        match = getattr(matcher, "match", None)
        if not callable(match):
            raise TypeError("matcher must expose match")
        self.matcher = matcher
        self.search_radius = radius
        self.displacement_min_quality = min_quality
        self.displacement_max_shift = max_shift
        self.max_global_jump = max_jump
        self.correction_frame_interval = frame_interval
        self.correction_distance = distance_interval
        self.correction_interval_ms = time_interval

    def _correction_due(
        self,
        frame: HybridFrame,
        previous_frame: HybridFrame,
        previous: AbsoluteRegistration,
        previous_position: tuple[float, float],
        motion_distance: float,
    ) -> tuple[bool, dict[str, object]]:
        """Return whether bounded shape correction should be attempted now."""
        enabled = any(
            (
                self.correction_frame_interval > 0,
                self.correction_distance > 0,
                self.correction_interval_ms > 0,
            )
        )
        if not enabled:
            return False, {}
        previous_metadata = dict(getattr(previous.result, "metadata", {}) or {})
        anchor_position = previous_metadata.get("last_correction_position")
        if not isinstance(anchor_position, (tuple, list)) or len(anchor_position) != 2:
            anchor_position = previous_position
        try:
            anchor_position = (float(anchor_position[0]), float(anchor_position[1]))
        except (TypeError, ValueError):
            anchor_position = previous_position
        anchor_frame = int(previous_metadata.get("last_correction_frame_id", previous_frame.frame_id))
        anchor_time = int(previous_metadata.get("last_correction_at_ms", previous_frame.captured_at_ms))
        frame_count = max(0, int(frame.frame_id) - anchor_frame)
        elapsed_ms = max(0, int(frame.captured_at_ms) - anchor_time)
        distance = math.dist(previous_position, anchor_position)
        motion_active = float(motion_distance) >= 0.2
        due = (
            (distance >= self.correction_distance if self.correction_distance > 0 else False)
            or (
                motion_active
                and (
                    (self.correction_frame_interval > 0 and frame_count >= self.correction_frame_interval)
                    or (self.correction_interval_ms > 0 and elapsed_ms >= self.correction_interval_ms)
                )
            )
        )
        return due, {
            "correction_due": due,
            "correction_frame_count": frame_count,
            "correction_elapsed_ms": elapsed_ms,
            "correction_distance": distance,
            "correction_motion_distance": float(motion_distance),
            "last_correction_position": anchor_position,
            "last_correction_frame_id": anchor_frame,
            "last_correction_at_ms": anchor_time,
        }

    def track(
        self,
        frame: HybridFrame,
        *,
        reference: Any,
        previous_frame: HybridFrame,
        previous: AbsoluteRegistration,
    ) -> AbsoluteRegistration | None:
        del reference
        fixed = previous.transform
        previous_mask = canonical_wall_mask(previous_frame.wall_mask)
        current_mask = canonical_wall_mask(frame.wall_mask)
        displacement = estimate_bounded_displacement(
            previous_mask,
            current_mask,
            min_quality=self.displacement_min_quality,
            max_shift=self.displacement_max_shift,
        )
        local_shift = displacement.shift
        previous_position = previous.result.position
        if previous_position is None:
            return None
        correction_due, correction_metadata = self._correction_due(
            frame,
            previous_frame,
            previous,
            previous_position,
            displacement.distance,
        )
        if displacement.accepted and local_shift is not None:
            global_shift = transform_local_displacement(
                local_shift,
                angle_degrees=fixed.angle_degrees,
                reflect_horizontal=fixed.reflect_horizontal,
                scale=fixed.scale,
            )
            position = (
                float(previous_position[0] - global_shift[0]),
                float(previous_position[1] - global_shift[1]),
            )
            jump = math.hypot(
                position[0] - previous_position[0],
                position[1] - previous_position[1],
            )
            if jump <= self.max_global_jump and not correction_due:
                translation = (
                    float(fixed.translation[0] - global_shift[0]),
                    float(fixed.translation[1] - global_shift[1]),
                )
                metadata = {
                    "shift": tuple(float(value) for value in local_shift),
                    "global_shift": global_shift,
                    "shift_dist": displacement.distance,
                    "displacement_quality": displacement.quality,
                    "displacement_reason": displacement.reason,
                    "position_jump": jump,
                }
                metadata.update(correction_metadata)
                return AbsoluteRegistration(
                    result=LocalizationResult(
                        position=position,
                        confidence=max(0.0, min(1.0, displacement.quality)),
                        source="visual_f2f",
                        registration_valid=True,
                        metadata=metadata,
                    ),
                    transform=SimilarityTransform2D(
                        angle_degrees=fixed.angle_degrees,
                        reflect_horizontal=fixed.reflect_horizontal,
                        scale=fixed.scale,
                        translation=translation,
                    ),
                    anchor_error=previous.anchor_error,
                    area_instance=previous.area_instance,
                    diagnostics=metadata,
                )

        transformed = transform_feature(
            current_mask,
            frame.local_player,
            angle=fixed.angle_degrees,
            reflect_horizontal=fixed.reflect_horizontal,
            scale=fixed.scale,
        )
        candidate = self.matcher.match(
            transformed.mask,
            origin=fixed.translation,
            radius=self.search_radius,
            scale=1.0,
        )
        origin = getattr(candidate, "frame_origin_global", None)
        if not bool(getattr(candidate, "valid", False)) or origin is None:
            if displacement.accepted and local_shift is not None and correction_due:
                global_shift = transform_local_displacement(
                    local_shift,
                    angle_degrees=fixed.angle_degrees,
                    reflect_horizontal=fixed.reflect_horizontal,
                    scale=fixed.scale,
                )
                position = (
                    float(previous_position[0] - global_shift[0]),
                    float(previous_position[1] - global_shift[1]),
                )
                jump = math.dist(position, previous_position)
                if jump <= self.max_global_jump:
                    metadata = {
                        "shift": tuple(float(value) for value in local_shift),
                        "global_shift": global_shift,
                        "shift_dist": displacement.distance,
                        "displacement_quality": displacement.quality,
                        "displacement_reason": displacement.reason,
                        "position_jump": jump,
                        "correction_attempted": True,
                        "correction_accepted": False,
                        "correction_reason": "bounded_match_failed",
                        "last_correction_position": position,
                        "last_correction_frame_id": frame.frame_id,
                        "last_correction_at_ms": frame.captured_at_ms,
                    }
                    return AbsoluteRegistration(
                        result=LocalizationResult(
                            position=position,
                            confidence=max(0.0, min(1.0, displacement.quality)),
                            source="visual_f2f",
                            registration_valid=True,
                            metadata=metadata,
                        ),
                        transform=SimilarityTransform2D(
                            angle_degrees=fixed.angle_degrees,
                            reflect_horizontal=fixed.reflect_horizontal,
                            scale=fixed.scale,
                            translation=(
                                float(fixed.translation[0] - global_shift[0]),
                                float(fixed.translation[1] - global_shift[1]),
                            ),
                        ),
                        anchor_error=previous.anchor_error,
                        area_instance=previous.area_instance,
                        diagnostics=metadata,
                    )
            return None
        if len(origin) != 2 or not all(math.isfinite(float(value)) for value in origin):
            return None
        top_left = float(origin[0]), float(origin[1])
        position = (
            top_left[0] + transformed.player_position[0],
            top_left[1] + transformed.player_position[1],
        )
        confidence = float(getattr(candidate, "confidence", 0.0))
        if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
            return None
        metadata = dict(getattr(candidate, "metadata", {}) or {})
        metadata.update(
            {
                "displacement_quality": displacement.quality,
                "displacement_distance": displacement.distance,
                "displacement_reason": displacement.reason,
                "search_radius": self.search_radius,
                "correction_attempted": bool(correction_due),
                "correction_accepted": True,
                "correction_reason": "bounded_match",
                "last_correction_position": position,
                "last_correction_frame_id": frame.frame_id,
                "last_correction_at_ms": frame.captured_at_ms,
            }
        )
        return AbsoluteRegistration(
            result=LocalizationResult(
                position=position,
                confidence=confidence,
                source="visual_local",
                registration_valid=True,
                metadata=metadata,
            ),
            transform=SimilarityTransform2D(
                angle_degrees=fixed.angle_degrees,
                reflect_horizontal=fixed.reflect_horizontal,
                scale=fixed.scale,
                translation=top_left,
            ),
            anchor_error=previous.anchor_error,
            area_instance=previous.area_instance,
            diagnostics=metadata,
        )


__all__ = ["VisualLocalTracker"]
