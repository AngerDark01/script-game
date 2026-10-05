"""Bounded online identification of stick input to native displacement."""

from __future__ import annotations

import math
from dataclasses import replace

import numpy as np

from .motion_models import MotionCalibrationState, MotionCommand, MotionResponse


class AdaptiveInputCalibrator:
    """Keep one robust RLS model per controller/role key."""

    def __init__(
        self,
        *,
        expected_speed: float = 80.0,
        forgetting_factor: float = 0.98,
        min_alignment: float = 0.20,
        min_displacement: float = 0.5,
        speed_smoothing: float = 0.20,
        max_parameter_step: float = 0.15,
    ) -> None:
        if expected_speed <= 0 or not 0.8 <= forgetting_factor <= 1.0:
            raise ValueError("invalid calibration speed or forgetting factor")
        if not 0.0 <= min_alignment <= 1.0 or min_displacement < 0.0:
            raise ValueError("invalid calibration acceptance gates")
        if not 0.0 < speed_smoothing <= 1.0 or max_parameter_step <= 0:
            raise ValueError("invalid calibration update limits")
        self.expected_speed = float(expected_speed)
        self.forgetting_factor = float(forgetting_factor)
        self.min_alignment = float(min_alignment)
        self.min_displacement = float(min_displacement)
        self.speed_smoothing = float(speed_smoothing)
        self.max_parameter_step = float(max_parameter_step)
        self._states: dict[str, MotionCalibrationState] = {}
        self._covariances: dict[str, np.ndarray] = {}

    def state_for(self, role_key: str) -> MotionCalibrationState:
        key = str(role_key).strip()
        if not key:
            raise ValueError("role_key is required")
        if key not in self._states:
            self._states[key] = MotionCalibrationState(role_key=key)
            self._covariances[key] = np.eye(2, dtype=np.float64) * 10.0
        return self._states[key]

    def update(self, command: MotionCommand, response: MotionResponse) -> MotionCalibrationState:
        if not isinstance(command, MotionCommand) or not isinstance(response, MotionResponse):
            raise TypeError("calibration requires MotionCommand and MotionResponse")
        state = self.state_for(command.role_key)
        displacement_norm = math.hypot(*response.displacement)
        if (
            not response.accepted
            or response.alignment < self.min_alignment
            or displacement_norm < self.min_displacement
            or math.hypot(*command.stick) < 1e-6
        ):
            return state
        phi = np.asarray(command.stick, dtype=np.float64)
        observation = np.asarray(response.displacement, dtype=np.float64) / (response.elapsed_ms / 1000.0)
        covariance = self._covariances[command.role_key]
        basis = np.asarray(state.stick_to_native, dtype=np.float64)
        denominator = self.forgetting_factor + float(phi.T @ covariance @ phi)
        gain = covariance @ phi / max(denominator, 1e-9)
        error = observation - basis @ phi
        candidate = basis + np.outer(error, gain)
        delta = np.clip(candidate - basis, -self.max_parameter_step, self.max_parameter_step)
        candidate = basis + delta
        updated_covariance = (covariance - np.outer(gain, phi @ covariance)) / self.forgetting_factor
        updated_covariance = np.clip(updated_covariance, -1e4, 1e4)
        speed_ratio = math.hypot(*response.displacement) / max(self.expected_speed * response.elapsed_ms / 1000.0, 1e-6)
        speed_gain = (1.0 - self.speed_smoothing) * state.speed_gain + self.speed_smoothing * speed_ratio
        confidence = min(1.0, state.confidence + 0.08)
        updated = replace(
            state,
            stick_to_native=candidate,
            speed_gain=float(np.clip(speed_gain, 0.25, 4.0)),
            duration_gain=float(np.clip(state.duration_gain / max(speed_ratio, 0.25), 0.25, 4.0)),
            confidence=confidence,
            sample_count=state.sample_count + 1,
            last_speed=math.hypot(*response.displacement) / (response.elapsed_ms / 1000.0),
            last_alignment=response.alignment,
        )
        self._states[command.role_key] = updated
        self._covariances[command.role_key] = updated_covariance
        return updated

    def native_to_stick(self, role_key: str, native_vector: tuple[float, float]) -> tuple[float, float]:
        """Convert a bounded native-space command through the current inverse basis."""
        state = self.state_for(role_key)
        vector = np.asarray(native_vector, dtype=np.float64)
        if vector.shape != (2,) or not np.isfinite(vector).all():
            raise ValueError("native_vector must contain two finite values")
        stick = np.linalg.pinv(np.asarray(state.stick_to_native, dtype=np.float64)) @ vector
        maximum = max(1.0, float(np.max(np.abs(stick))))
        result = np.clip(stick / maximum, -1.0, 1.0)
        return float(result[0]), float(result[1])

    def reset(self, role_key: str | None = None) -> None:
        if role_key is None:
            self._states.clear()
            self._covariances.clear()
            return
        key = str(role_key).strip()
        self._states.pop(key, None)
        self._covariances.pop(key, None)


__all__ = ["AdaptiveInputCalibrator"]
