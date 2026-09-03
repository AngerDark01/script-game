from __future__ import annotations

from typing import TYPE_CHECKING

from .builtins import create_default_algorithm_registry
from .models import FrameContext, PerceptionRunResult
from .profiles import TargetProfile
from .registry import AlgorithmRegistry
from .stages.confirmation import ConfirmationTracker
from .stages.fusion import fuse_candidates
from .stages.runner import DetectorRunner
from .stages.selection import select_candidate

if TYPE_CHECKING:
    from .pipeline import PerceptionPipeline


ProfileKey = tuple[str, str, str]


class PerceptionEngine:
    """Target-level facade for profile-driven perception.

    The engine is the stable seam used by applications and workflows. It owns
    profile lookup, generic decision-stage composition, and confirmation state.
    It never performs input actions or imports GUI code.
    """

    def __init__(
        self,
        registry: AlgorithmRegistry | None = None,
        pipeline: PerceptionPipeline | None = None,
    ) -> None:
        if pipeline is not None and registry is not None and pipeline.registry is not registry:
            raise ValueError("pipeline and registry must refer to the same registry")
        self.registry = registry or (pipeline.registry if pipeline is not None else create_default_algorithm_registry())
        self._compatibility_pipeline = pipeline
        self.runner = DetectorRunner(self.registry)
        self.confirmation = ConfirmationTracker()
        self._profiles: dict[ProfileKey, TargetProfile] = {}

    def detect(
        self,
        frame: FrameContext,
        profile: TargetProfile,
        *,
        reference: tuple[float, float] | None = None,
    ) -> PerceptionRunResult:
        """Run one target profile against one normalized frame."""
        if not isinstance(frame, FrameContext):
            raise TypeError("frame must be a FrameContext")
        if not isinstance(profile, TargetProfile):
            raise TypeError("profile must be a TargetProfile")
        if self._compatibility_pipeline is not None:
            return self._compatibility_pipeline.run(frame, profile, reference=reference)
        return self._run_stages(frame, profile, reference=reference)

    def detect_target(
        self,
        frame: FrameContext,
        *,
        game_id: str,
        scene_id: str,
        target_type: str,
        reference: tuple[float, float] | None = None,
    ) -> PerceptionRunResult:
        """Resolve a registered game/scene/target profile and run it."""
        profile = self.resolve_profile(game_id, scene_id, target_type)
        return self.detect(frame, profile, reference=reference)

    def register_profile(self, profile: TargetProfile, *, replace: bool = False) -> ProfileKey:
        """Register a defensive copy of a target profile.

        A duplicate key is rejected by default so accidental profile shadowing
        cannot silently change a running workflow. Callers that intentionally
        update a profile must opt into ``replace=True``.
        """
        if not isinstance(profile, TargetProfile):
            raise TypeError("profile must be a TargetProfile")
        key = self.profile_key(profile.game_id, profile.scene_id, profile.target_type)
        if key in self._profiles and not replace:
            raise ValueError(f"profile already registered: {key}")
        if key in self._profiles:
            self.reset_confirmation(profile)
        self._profiles[key] = profile.copy()
        return key

    def unregister_profile(self, game_id: str, scene_id: str, target_type: str) -> TargetProfile:
        """Remove and return a defensive copy of a registered profile."""
        key = self.profile_key(game_id, scene_id, target_type)
        try:
            profile = self._profiles.pop(key)
        except KeyError as exc:
            raise KeyError(f"profile not registered: {key}") from exc
        self.reset_confirmation(profile)
        return profile.copy()

    def resolve_profile(self, game_id: str, scene_id: str, target_type: str) -> TargetProfile:
        """Return a defensive copy of the profile for one target key."""
        key = self.profile_key(game_id, scene_id, target_type)
        try:
            return self._profiles[key].copy()
        except KeyError as exc:
            raise KeyError(f"profile not registered: {key}") from exc

    def profiles(self) -> tuple[TargetProfile, ...]:
        """Return registered profiles in insertion order as defensive copies."""
        return tuple(profile.copy() for profile in self._profiles.values())

    def descriptors(self):
        """Return the algorithm catalog exposed by the configured registry."""
        return tuple(self.registry.descriptors())

    def reset_confirmation(self, profile: TargetProfile | None = None) -> None:
        """Clear one target's temporal state or all engine confirmation state."""
        if self._compatibility_pipeline is not None:
            self._compatibility_pipeline.reset_confirmation(profile)
            return
        key = None if profile is None else (profile.game_id, profile.scene_id, profile.target_type)
        self.confirmation.reset(key)

    def _run_stages(
        self,
        frame: FrameContext,
        profile: TargetProfile,
        *,
        reference: tuple[float, float] | None,
    ) -> PerceptionRunResult:
        raw = self.runner.run(frame=frame, profile=profile)
        candidates = tuple(item for item in raw.candidates if float(item.confidence) >= float(profile.min_confidence))
        merge_radius = max(0.0, float(profile.metadata.get("merge_radius", 12.0)))
        fused = fuse_candidates(candidates, merge_radius)
        confirmation = self.confirmation.observe(
            (profile.game_id, profile.scene_id, profile.target_type),
            fused,
            required_frames=profile.confirmation_frames,
            match_radius=merge_radius,
        )
        return PerceptionRunResult(
            detections=confirmation.detections,
            by_algorithm=raw.by_algorithm,
            errors=raw.errors,
            selected=select_candidate(confirmation.detections, profile.selection_strategy, reference=reference),
            confirmed=confirmation.confirmed,
            confirmation_counts=confirmation.counts,
        )

    @staticmethod
    def profile_key(game_id: str, scene_id: str, target_type: str) -> ProfileKey:
        values = (str(game_id).strip(), str(scene_id).strip(), str(target_type).strip())
        if not all(values):
            raise ValueError("game_id, scene_id, and target_type must not be empty")
        return values
