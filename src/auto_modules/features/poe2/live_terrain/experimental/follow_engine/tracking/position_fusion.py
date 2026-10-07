"""Prediction/observation fusion with innovation gating."""

from __future__ import annotations

import math
from dataclasses import dataclass


def _point(value: tuple[float, float]) -> tuple[float, float]:
    point = (float(value[0]), float(value[1]))
    if not all(math.isfinite(item) for item in point):
        raise ValueError("point must contain finite values")
    return point


def predict_position(
    position: tuple[float, float],
    visual_velocity: tuple[float, float],
    command_velocity: tuple[float, float],
    dt_seconds: float,
    *,
    visual_weight: float = 0.7,
    command_weight: float = 0.3,
) -> tuple[float, float]:
    dt = max(0.0, float(dt_seconds))
    if not math.isfinite(dt):
        raise ValueError("dt_seconds must be finite")
    if visual_weight < 0.0 or command_weight < 0.0:
        raise ValueError("prediction weights must be non-negative")
    start = _point(position)
    visual = _point(visual_velocity)
    command = _point(command_velocity)
    velocity = (
        visual[0] * visual_weight + command[0] * command_weight,
        visual[1] * visual_weight + command[1] * command_weight,
    )
    return (start[0] + velocity[0] * dt, start[1] + velocity[1] * dt)


def fuse_position(
    predicted: tuple[float, float],
    observed: tuple[float, float],
    *,
    prediction_sigma: float,
    observation_sigma: float,
) -> tuple[float, float]:
    pred = _point(predicted)
    obs = _point(observed)
    pred_sigma = max(0.0, float(prediction_sigma))
    obs_sigma = max(0.0, float(observation_sigma))
    if not math.isfinite(pred_sigma) or not math.isfinite(obs_sigma):
        raise ValueError("sigma values must be finite")
    pred_var = pred_sigma**2
    obs_var = obs_sigma**2
    gain = 0.5 if pred_var + obs_var == 0.0 else pred_var / (pred_var + obs_var)
    return ((1.0 - gain) * pred[0] + gain * obs[0], (1.0 - gain) * pred[1] + gain * obs[1])


@dataclass(frozen=True, slots=True)
class FusionResult:
    position: tuple[float, float]
    accepted: bool
    innovation: float
    gain: float
    uncertainty: float


def fuse_observation(
    predicted: tuple[float, float],
    observed: tuple[float, float],
    *,
    prediction_sigma: float,
    observation_sigma: float,
    max_innovation: float,
    observation_confidence: float = 1.0,
) -> FusionResult:
    pred = _point(predicted)
    obs = _point(observed)
    innovation = math.dist(pred, obs)
    max_error = float(max_innovation)
    confidence = float(observation_confidence)
    if max_error < 0.0 or not math.isfinite(max_error) or not 0.0 <= confidence <= 1.0:
        raise ValueError("innovation gate parameters are invalid")
    accepted = innovation <= max_error and confidence > 0.0
    pred_sigma = max(0.0, float(prediction_sigma))
    obs_sigma = max(0.0, float(observation_sigma))
    pred_var = pred_sigma**2
    obs_var = obs_sigma**2
    gain = 0.5 if pred_var + obs_var == 0.0 else pred_var / (pred_var + obs_var)
    if not accepted:
        return FusionResult(pred, False, innovation, 0.0, pred_sigma)
    position = fuse_position(pred, obs, prediction_sigma=pred_sigma, observation_sigma=obs_sigma)
    uncertainty = (1.0 - gain) * pred_sigma + gain * obs_sigma
    return FusionResult(position, True, innovation, gain, uncertainty)


def grow_uncertainty(
    fused_sigma: float,
    *,
    visual_gap_ms: float,
    speed_error_units_per_second: float,
    command_duration_ms: float,
    command_error_units_per_second: float,
) -> float:
    values = tuple(float(value) for value in (fused_sigma, visual_gap_ms, speed_error_units_per_second, command_duration_ms, command_error_units_per_second))
    if not all(math.isfinite(value) for value in values):
        raise ValueError("uncertainty inputs must be finite")
    base, gap, speed_error, duration, command_error = values
    if min(values) < 0.0:
        raise ValueError("uncertainty inputs must be non-negative")
    return base + speed_error * gap / 1000.0 + command_error * duration / 1000.0
