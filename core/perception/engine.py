from __future__ import annotations

from .builtins import create_default_algorithm_registry
from .models import FrameContext
from .pipeline import PerceptionPipeline, PerceptionRunResult
from .profiles import TargetProfile
from .registry import AlgorithmRegistry


ProfileKey = tuple[str, str, str]


class PerceptionEngine:
    """Target-level facade for profile-driven perception.

    The engine is the stable seam used by applications and workflows. It owns
    profile lookup and keeps the current pipeline implementation behind one
    target-oriented entry point. It never performs input actions or imports GUI
    code.
    """

    def __init__(
        self,
        registry: AlgorithmRegistry | None = None,
        pipeline: PerceptionPipeline | None = None,
    ) -> None:
        if pipeline is not None and registry is not None and pipeline.registry is not registry:
            raise ValueError("pipeline and registry must refer to the same registry")
        self.registry = registry or (pipeline.registry if pipeline is not None else create_default_algorithm_registry())
        self.pipeline = pipeline or PerceptionPipeline(self.registry)
        self._profiles: dict[ProfileKey, TargetProfile] = {}

    def detect(self, frame: FrameContext, profile: TargetProfile) -> PerceptionRunResult:
        """Run one target profile against one normalized frame."""
        if not isinstance(frame, FrameContext):
            raise TypeError("frame must be a FrameContext")
        if not isinstance(profile, TargetProfile):
            raise TypeError("profile must be a TargetProfile")
        return self.pipeline.run(frame, profile)

    def detect_target(
        self,
        frame: FrameContext,
        *,
        game_id: str,
        scene_id: str,
        target_type: str,
    ) -> PerceptionRunResult:
        """Resolve a registered game/scene/target profile and run it."""
        profile = self.resolve_profile(game_id, scene_id, target_type)
        return self.detect(frame, profile)

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
        self._profiles[key] = profile.copy()
        return key

    def unregister_profile(self, game_id: str, scene_id: str, target_type: str) -> TargetProfile:
        """Remove and return a defensive copy of a registered profile."""
        key = self.profile_key(game_id, scene_id, target_type)
        try:
            profile = self._profiles.pop(key)
        except KeyError as exc:
            raise KeyError(f"profile not registered: {key}") from exc
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

    @staticmethod
    def profile_key(game_id: str, scene_id: str, target_type: str) -> ProfileKey:
        values = (str(game_id).strip(), str(scene_id).strip(), str(target_type).strip())
        if not all(values):
            raise ValueError("game_id, scene_id, and target_type must not be empty")
        return values
