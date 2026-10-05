import math

import cv2
import numpy as np

from .route_progress import (
    build_cumulative_lengths as _build_cumulative_lengths,
)
from .route_progress import (
    interpolate_by_distance as _interpolate_by_distance,
)
from .route_progress import (
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


def line_is_walkable(wall_map, start, end, obstacle_threshold: int = 1, *, corner_safe: bool = False) -> bool:
    height, width = wall_map.shape[:2]
    previous = None
    for x, y in _bresenham_points(start, end):
        if x < 0 or y < 0 or x >= width or y >= height:
            return False
        if int(wall_map[y, x]) >= obstacle_threshold:
            return False
        if corner_safe and previous is not None:
            px, py = previous
            if px != x and py != y and (int(wall_map[py, x]) >= obstacle_threshold or int(wall_map[y, px]) >= obstacle_threshold):
                return False
        previous = (x, y)
    return True


def line_min_clearance(
    wall_map,
    start,
    end,
    *,
    obstacle_threshold: int = 1,
    distance_map=None,
) -> float:
    """Return the minimum map-space distance from a segment to an obstacle.

    ``line_is_walkable`` answers the hard collision question.  This companion
    check answers the separate safety question and lets a caller reject a
    route that technically stays walkable while scraping a wall.  The
    distance transform is calculated per call because this function is used
    at route-validation boundaries; high-frequency tracking should cache the
    resulting verdict rather than call it for every stick tick.
    """
    values = np.asarray(wall_map)
    if values.ndim != 2:
        raise ValueError("wall_map must be two-dimensional")
    if distance_map is None:
        free = np.where(values >= obstacle_threshold, 0, 255).astype(np.uint8)
        distance = cv2.distanceTransform(free, cv2.DIST_L2, 3)
    else:
        distance = np.asarray(distance_map)
        if distance.shape != values.shape:
            raise ValueError("distance_map shape must match wall_map")
    height, width = values.shape
    minimum = float("inf")
    for x, y in _bresenham_points(start, end):
        if x < 0 or y < 0 or x >= width or y >= height:
            return 0.0
        minimum = min(minimum, float(distance[y, x]))
    return 0.0 if minimum == float("inf") else minimum


def line_clearance_stats(
    wall_map,
    start,
    end,
    *,
    obstacle_threshold: int = 1,
    distance_map=None,
    clearance_band: float = 0.0,
):
    """Measure the clearance profile along a route segment.

    A minimum alone overreacts to one raster cell and misses a long stretch
    that scrapes a wall.  The returned mean and low-clearance fraction let
    planners prefer an open corridor while still accepting a doorway when it
    is the only connection.
    """
    values = np.asarray(wall_map)
    if values.ndim != 2:
        raise ValueError("wall_map must be two-dimensional")
    if distance_map is None:
        free = np.where(values >= obstacle_threshold, 0, 255).astype(np.uint8)
        distance = cv2.distanceTransform(free, cv2.DIST_L2, 3)
    else:
        distance = np.asarray(distance_map)
        if distance.shape != values.shape:
            raise ValueError("distance_map shape must match wall_map")
    samples = []
    height, width = values.shape
    for x, y in _bresenham_points(start, end):
        if x < 0 or y < 0 or x >= width or y >= height:
            return {"minimum": 0.0, "mean": 0.0, "low_fraction": 1.0, "samples": len(samples)}
        samples.append(float(distance[y, x]))
    if not samples:
        return {"minimum": 0.0, "mean": 0.0, "low_fraction": 1.0, "samples": 0}
    band = max(0.0, float(clearance_band))
    return {
        "minimum": min(samples),
        "mean": sum(samples) / len(samples),
        "low_fraction": (
            sum(value < band for value in samples) / len(samples)
            if band > 0.0 else 0.0
        ),
        "samples": len(samples),
    }


def shortcut_path(wall_map, path, *, corner_safe: bool = False):
    if len(path) <= 2:
        return list(path)

    simplified = []
    anchor = 0
    last_index = len(path) - 1

    while anchor < last_index:
        simplified.append(path[anchor])
        probe = last_index
        while probe > anchor + 1:
            if line_is_walkable(wall_map, path[anchor], path[probe], corner_safe=corner_safe):
                break
            probe -= 1
        anchor = probe

    simplified.append(path[-1])
    return simplified


def smooth_path(wall_map, path, *, corner_safe: bool = False):
    if not path:
        return []
    return shortcut_path(wall_map, remove_collinear_points(path), corner_safe=corner_safe)


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
