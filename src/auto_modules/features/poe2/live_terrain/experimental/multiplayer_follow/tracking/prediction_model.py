"""Small, dependency-free prediction and observation fusion functions."""

from __future__ import annotations


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
    velocity = (
        float(visual_velocity[0]) * visual_weight + float(command_velocity[0]) * command_weight,
        float(visual_velocity[1]) * visual_weight + float(command_velocity[1]) * command_weight,
    )
    return (float(position[0]) + velocity[0] * dt, float(position[1]) + velocity[1] * dt)


def fuse_position(
    predicted: tuple[float, float],
    observed: tuple[float, float],
    *,
    prediction_sigma: float,
    observation_sigma: float,
) -> tuple[float, float]:
    pred_var = max(0.0, float(prediction_sigma)) ** 2
    obs_var = max(0.0, float(observation_sigma)) ** 2
    gain = 0.5 if pred_var + obs_var == 0 else pred_var / (pred_var + obs_var)
    return (
        (1 - gain) * float(predicted[0]) + gain * float(observed[0]),
        (1 - gain) * float(predicted[1]) + gain * float(observed[1]),
    )


__all__ = ["fuse_position", "predict_position"]
