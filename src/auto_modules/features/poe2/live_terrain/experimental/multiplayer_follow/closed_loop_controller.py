"""Sequential local motion policy for the PoE2 experimental page."""

from __future__ import annotations

import math
from dataclasses import dataclass
from types import MappingProxyType

from auto_modules.core.routing.local_controller import LocalMotionController

from .complexity import ComplexityDecision, ComplexityState, LocalComplexityClassifier
from .motion_calibration import AdaptiveInputCalibrator
from .motion_models import MotionCalibrationState, MotionCommand, MotionPhase, MotionResponse
from .motion_snapshot import MotionSnapshot
from .sequential_motion import SequentialMotionEstimator, SequentialMotionUpdate


@dataclass(frozen=True, slots=True)
class ClosedLoopDecision:
    phase: MotionPhase
    command: MotionCommand | None
    complexity: ComplexityDecision
    calibration: MotionCalibrationState
    estimator: SequentialMotionUpdate | None
    diagnostics: dict[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "diagnostics", MappingProxyType(dict(self.diagnostics)))


class ClosedLoopMotionController:
    """Combine local geometry, sequential feedback and adaptive input mapping."""

    def __init__(
        self,
        *,
        classifier: LocalComplexityClassifier | None = None,
        calibrator: AdaptiveInputCalibrator | None = None,
        local_controller: LocalMotionController | None = None,
        expected_speed: float = 80.0,
        arrival_radius: float = 8.0,
        open_stick_magnitude: float = 0.65,
        open_duration_ms: int = 160,
        transition_duration_ms: int = 100,
        constrained_duration_ms: int = 70,
        max_frame_age_ms: int = 500,
    ) -> None:
        if expected_speed <= 0 or arrival_radius <= 0:
            raise ValueError("expected_speed and arrival_radius must be positive")
        if not 0.0 < open_stick_magnitude <= 1.0:
            raise ValueError("open_stick_magnitude must be in (0, 1]")
        if min(open_duration_ms, transition_duration_ms, constrained_duration_ms) <= 0:
            raise ValueError("command durations must be positive")
        if int(max_frame_age_ms) <= 0:
            raise ValueError("max_frame_age_ms must be positive")
        self.expected_speed = float(expected_speed)
        self.arrival_radius = float(arrival_radius)
        self.open_stick_magnitude = float(open_stick_magnitude)
        self.open_duration_ms = int(open_duration_ms)
        self.transition_duration_ms = int(transition_duration_ms)
        self.constrained_duration_ms = int(constrained_duration_ms)
        self.classifier = classifier or LocalComplexityClassifier(
            max_frame_age_ms=int(max_frame_age_ms),
        )
        self._classifiers: dict[str, LocalComplexityClassifier] = {}
        self.calibrator = calibrator or AdaptiveInputCalibrator(expected_speed=expected_speed)
        self.local_controller = local_controller or LocalMotionController(
            expected_speed=expected_speed, arrival_radius=arrival_radius,
        )
        self._estimators: dict[str, SequentialMotionEstimator] = {}
        self._map_versions: dict[str, str] = {}
        self._command_id = 0
        self._last_commands: dict[str, MotionCommand] = {}

    def step(self, snapshot: MotionSnapshot, *, now_ms: int) -> ClosedLoopDecision:
        if not isinstance(snapshot, MotionSnapshot):
            raise TypeError("snapshot must be MotionSnapshot")
        observation = snapshot.observation
        role_key = observation.role_key
        calibration = self.calibrator.state_for(role_key)
        estimator = self._estimators.setdefault(role_key, SequentialMotionEstimator(min_displacement=0.5))
        if self._map_versions.get(role_key) != observation.map_version or estimator.position is None:
            estimator.reset(observation.position, now_ms=observation.captured_at_ms)
            self._map_versions[role_key] = observation.map_version
            # A new map/registration starts a new temporal complexity history.
            # Reusing constrained hysteresis from the previous instance can
            # force a fresh spawn into candidate-pulse mode for several ticks.
            self._classifiers.pop(role_key, None)
        # Complexity hysteresis is per role.  Sharing one classifier would
        # allow P1's narrow corridor to change P2's policy on the next tick.
        role_classifier = self._classifiers.setdefault(role_key, self.classifier.clone())
        complexity = role_classifier.classify(snapshot)
        target_distance = math.hypot(observation.target[0] - observation.position[0], observation.target[1] - observation.position[1])
        if target_distance <= self.arrival_radius:
            return self._decision(MotionPhase.ARRIVED, None, complexity, calibration, None, "arrived")
        if complexity.state is ComplexityState.UNKNOWN:
            return self._decision(MotionPhase.STOPPED, None, complexity, calibration, None, "local_observation_unknown")
        target_delta = (observation.target[0] - observation.position[0], observation.target[1] - observation.position[1])
        norm = math.hypot(*target_delta)
        direct = (target_delta[0] / norm, target_delta[1] / norm)
        policy = "regulated_pursuit"
        if complexity.state is ComplexityState.OPEN:
            native_vector = (direct[0] * self.open_stick_magnitude, direct[1] * self.open_stick_magnitude)
            duration = self.open_duration_ms
        else:
            local = self.local_controller.command(
                observation.position,
                observation.target,
                snapshot.route,
                desired_vector=direct,
                walls=snapshot.wall_map,
                distance_map=snapshot.distance_field,
                observed_velocity=observation.observed_velocity,
                confidence=observation.confidence,
                arrival_radius=self.arrival_radius,
            )
            if local.vector == (0.0, 0.0):
                return self._decision(MotionPhase.RECOVERING, None, complexity, calibration, None, local.diagnostics.get("reason", "local_controller_blocked"), policy="candidate_pulse")
            native_vector = local.vector
            duration = self.constrained_duration_ms if complexity.state is ComplexityState.CONSTRAINED else self.transition_duration_ms
            policy = "candidate_pulse" if complexity.state is ComplexityState.CONSTRAINED else "blended_transition"
            if complexity.state is ComplexityState.TRANSITION:
                native_vector = ((native_vector[0] + direct[0] * self.open_stick_magnitude) * 0.5, (native_vector[1] + direct[1] * self.open_stick_magnitude) * 0.5)
        duration = int(max(20, min(300, duration * calibration.duration_gain)))
        stick = self.calibrator.native_to_stick(role_key, native_vector)
        self._command_id += 1
        command = MotionCommand(
            command_id=self._command_id,
            role_key=role_key,
            desired_native_vector=native_vector,
            stick=stick,
            duration_ms=duration,
            issued_at_ms=int(now_ms),
            map_version=observation.map_version,
        )
        self._last_commands[role_key] = command
        return self._decision(MotionPhase.ISSUE_COMMAND, command, complexity, calibration, None, "command_ready", policy=policy)

    def record_response(self, command: MotionCommand, response: MotionResponse, *, now_ms: int) -> SequentialMotionUpdate:
        if command.map_version != self._map_versions.get(command.role_key):
            raise ValueError("motion response belongs to a stale map version")
        self.calibrator.update(command, response)
        estimator = self._estimators.get(command.role_key)
        if estimator is None:
            raise RuntimeError("motion estimator is not initialized for command role")
        return estimator.apply(command, response, now_ms=now_ms)

    def _decision(self, phase, command, complexity, calibration, estimator, reason, *, policy="neutral"):
        return ClosedLoopDecision(
            phase=phase,
            command=command,
            complexity=complexity,
            calibration=calibration,
            estimator=estimator,
            diagnostics={
                "reason": reason,
                "policy": policy,
                "complexity": complexity.score,
                "complexity_state": complexity.state.value,
                "calibration_confidence": calibration.confidence,
                "calibration_samples": calibration.sample_count,
            },
        )


__all__ = ["ClosedLoopDecision", "ClosedLoopMotionController"]
