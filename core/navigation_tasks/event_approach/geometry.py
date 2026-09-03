from __future__ import annotations

from core.routing.geometry import build_cumulative_lengths, interpolate_by_distance


def float_point_or_none(point) -> tuple[float, float] | None:
    if point is None:
        return None
    return (float(point[0]), float(point[1]))


def int_point_or_none(point) -> tuple[int, int] | None:
    if point is None:
        return None
    return (int(round(float(point[0]))), int(round(float(point[1]))))


def is_event_in_real_view(config, player, target) -> bool:
    half = max(1.0, float(config.game_view_map_size) * 0.5)
    margin = max(0.0, float(config.visible_margin))
    return (
        float(player[0]) - half - margin <= float(target[0]) <= float(player[0]) + half + margin
        and float(player[1]) - half - margin <= float(target[1]) <= float(player[1]) + half + margin
    )


def approach_target_from_path(config, path, target) -> tuple[float, float] | None:
    if not path:
        return target
    clean_path = [float_point_or_none(point) for point in path]
    if len(clean_path) < 2:
        return clean_path[0]
    lengths = build_cumulative_lengths(clean_path)
    total = lengths[-1] if lengths else 0.0
    stop_distance = max(8.0, float(config.stop_radius))
    if total <= stop_distance:
        return clean_path[-1]
    return interpolate_by_distance(clean_path, lengths, total - stop_distance) or clean_path[-1]


def approach_target_from_path_with_stop_radius(config, path, target, stop_radius: float) -> tuple[float, float] | None:
    if not path:
        return target
    clean_path = [float_point_or_none(point) for point in path]
    if len(clean_path) < 2:
        return clean_path[0]
    lengths = build_cumulative_lengths(clean_path)
    total = lengths[-1] if lengths else 0.0
    stop_distance = max(8.0, float(stop_radius))
    if total <= stop_distance:
        return clean_path[-1]
    return interpolate_by_distance(clean_path, lengths, total - stop_distance) or clean_path[-1]
