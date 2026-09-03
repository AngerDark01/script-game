from __future__ import annotations

from core.routing.geometry import point_distance

from .utils import float_point


def local_probe(executor, current_pos, target_pos):
    distance = point_distance(current_pos, target_pos)
    if distance <= 1e-6:
        return float_point(target_pos)

    dx = float(target_pos[0]) - float(current_pos[0])
    dy = float(target_pos[1]) - float(current_pos[1])
    ux = dx / distance
    uy = dy / distance
    px = -uy
    py = ux
    side_pattern = (0.0, -1.0, 1.0)
    side = side_pattern[executor.probe_index % len(side_pattern)]
    executor.probe_index += 1
    forward = min(distance, max(0.0, float(getattr(executor, "local_probe_forward_distance", 84.0))))
    lateral = max(0.0, float(getattr(executor, "local_probe_lateral_distance", 44.0))) if side else 0.0
    return (
        float(current_pos[0]) + ux * forward + px * side * lateral,
        float(current_pos[1]) + uy * forward + py * side * lateral,
    )


def is_movement_stuck(executor, current_progress: float, now_ms: int) -> bool:
    if executor.last_progress_value is None or executor.last_progress_ms <= 0:
        executor.last_progress_value = float(current_progress)
        executor.last_progress_ms = int(now_ms)
        return False

    if float(current_progress) - float(executor.last_progress_value) >= executor.min_progress_delta:
        executor.last_progress_value = float(current_progress)
        executor.last_progress_ms = int(now_ms)
        executor.recover_attempts = 0
        return False

    return int(now_ms) - int(executor.last_progress_ms) >= executor.progress_timeout_ms


def recovery_probe(executor, current_pos, target_pos, *, attempt: int):
    distance = point_distance(current_pos, target_pos)
    if distance <= 1e-6:
        return float_point(target_pos)

    dx = float(target_pos[0]) - float(current_pos[0])
    dy = float(target_pos[1]) - float(current_pos[1])
    ux = dx / distance
    uy = dy / distance
    px = -uy
    py = ux
    side_pattern = (-1.0, 1.0, 0.0)
    side = side_pattern[int(attempt) % len(side_pattern)]
    forward_min = max(0.0, float(getattr(executor, "recovery_probe_forward_min", 36.0)))
    forward_max = max(forward_min, float(getattr(executor, "recovery_probe_forward_max", 72.0)))
    forward_multiplier = max(0.0, float(getattr(executor, "recovery_probe_forward_multiplier", 1.6)))
    forward = min(max(executor.anchor_arrival_radius * forward_multiplier, forward_min), forward_max)
    lateral = max(0.0, float(getattr(executor, "recovery_probe_lateral_distance", 58.0))) if side else 0.0
    return (
        float(current_pos[0]) + ux * forward + px * side * lateral,
        float(current_pos[1]) + uy * forward + py * side * lateral,
    )
