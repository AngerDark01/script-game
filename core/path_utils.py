import math


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
    if not path:
        return []

    cumulative = [0.0]
    for index in range(1, len(path)):
        cumulative.append(cumulative[-1] + point_distance(path[index - 1], path[index]))
    return cumulative


def project_point_onto_path(point, path, cumulative=None):
    if not path:
        return None
    if len(path) == 1:
        return {
            "point": tuple(path[0]),
            "segment_index": 0,
            "distance": 0.0,
            "distance_to_path": point_distance(point, path[0]),
        }

    cumulative = cumulative or build_cumulative_lengths(path)
    px, py = float(point[0]), float(point[1])
    best = None

    for index in range(len(path) - 1):
        ax, ay = float(path[index][0]), float(path[index][1])
        bx, by = float(path[index + 1][0]), float(path[index + 1][1])
        vx, vy = bx - ax, by - ay
        seg_len_sq = vx * vx + vy * vy
        if seg_len_sq == 0:
            t = 0.0
        else:
            t = ((px - ax) * vx + (py - ay) * vy) / seg_len_sq
            t = max(0.0, min(1.0, t))

        proj_x = ax + t * vx
        proj_y = ay + t * vy
        deviation = math.hypot(px - proj_x, py - proj_y)
        path_distance = cumulative[index] + point_distance((ax, ay), (proj_x, proj_y))

        candidate = {
            "point": (proj_x, proj_y),
            "segment_index": index,
            "distance": path_distance,
            "distance_to_path": deviation,
        }
        if best is None or candidate["distance_to_path"] < best["distance_to_path"]:
            best = candidate

    return best


def interpolate_by_distance(path, cumulative, distance):
    if not path:
        return None
    if len(path) == 1:
        return tuple(path[0])

    clamped = max(0.0, min(float(distance), cumulative[-1]))
    for index in range(len(cumulative) - 1):
        start_distance = cumulative[index]
        end_distance = cumulative[index + 1]
        if clamped <= end_distance:
            span = end_distance - start_distance
            ratio = 0.0 if span == 0 else (clamped - start_distance) / span
            ax, ay = path[index]
            bx, by = path[index + 1]
            return (ax + (bx - ax) * ratio, ay + (by - ay) * ratio)

    return tuple(path[-1])


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
