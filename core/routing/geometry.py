import math

from .route_progress import (
    build_cumulative_lengths as _build_cumulative_lengths,
    interpolate_by_distance as _interpolate_by_distance,
    project_point_on_polyline,
)


def point_distance(a, b) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def remove_collinear_points(path):
    if len(path) <= 2:
        return list(path)

    result = [path[0]]
    for index in range(1, len(path) - 1):
        ax, ay = result[-1]
        bx, by = path[index]
        cx, cy = path[index + 1]
        abx, aby = bx - ax, by - ay
        bcx, bcy = cx - bx, cy - by
        cross = abx * bcy - aby * bcx
        if cross == 0:
            continue
        result.append(path[index])

    result.append(path[-1])
    return result


def _bresenham_points(start, end):
    x1, y1 = int(round(start[0])), int(round(start[1]))
    x2, y2 = int(round(end[0])), int(round(end[1]))

    dx = abs(x2 - x1)
    dy = -abs(y2 - y1)
    sx = 1 if x1 < x2 else -1
    sy = 1 if y1 < y2 else -1
    err = dx + dy

    while True:
        yield x1, y1
        if x1 == x2 and y1 == y2:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x1 += sx
        if e2 <= dx:
            err += dx
            y1 += sy


def line_is_walkable(wall_map, start, end, obstacle_threshold: int = 1) -> bool:
    height, width = wall_map.shape[:2]
    for x, y in _bresenham_points(start, end):
        if x < 0 or y < 0 or x >= width or y >= height:
            return False
        if int(wall_map[y, x]) >= obstacle_threshold:
            return False
    return True


def shortcut_path(wall_map, path):
    if len(path) <= 2:
        return list(path)

    simplified = []
    anchor = 0
    last_index = len(path) - 1

    while anchor < last_index:
        simplified.append(path[anchor])
        probe = last_index
        while probe > anchor + 1:
            if line_is_walkable(wall_map, path[anchor], path[probe]):
                break
            probe -= 1
        anchor = probe

    simplified.append(path[-1])
    return simplified


def smooth_path(wall_map, path):
    if not path:
        return []
    return shortcut_path(wall_map, remove_collinear_points(path))


def build_cumulative_lengths(path):
    return _build_cumulative_lengths(path)


def project_point_onto_path(point, path, cumulative=None):
    projection = project_point_on_polyline(point, path, cumulative)
    if projection is None:
        return None
    return {
        "point": projection.point if len(path) > 1 else tuple(path[0]),
        "segment_index": projection.segment_index,
        "distance": projection.progress,
        "distance_to_path": projection.deviation,
    }


def interpolate_by_distance(path, cumulative, distance):
    return _interpolate_by_distance(path, cumulative, distance)


def distance_to_path(point, path, cumulative=None) -> float:
    projection = project_point_onto_path(point, path, cumulative)
    if projection is None:
        return float("inf")
    return projection["distance_to_path"]


def is_inside_exit_region(point, region) -> bool:
    if not region:
        return False
    cx, cy = region["center"]
    radius = float(region["radius"])
    dx = float(point[0]) - float(cx)
    dy = float(point[1]) - float(cy)
    return dx * dx + dy * dy <= radius * radius
