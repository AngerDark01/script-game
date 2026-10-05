"""Holonomic top-down path tracking; no differential-drive turn model.

Returns a normalized map-space movement vector. Coordinate conversion to a
physical device belongs to an output adapter, not to path planning.
"""
from itertools import pairwise
from math import hypot, isfinite

from auto_modules.core.routing.geometry import (
    build_cumulative_lengths,
    interpolate_by_distance,
    line_is_walkable,
    point_distance,
    project_point_onto_path,
)


class VectorPathTracker:
    def __init__(self, *, lookahead=12., arrival_radius=3., slowdown_distance=20., max_magnitude=1.):
        if not all(isfinite(x) and x > 0 for x in (lookahead, arrival_radius, slowdown_distance, max_magnitude)) or max_magnitude > 1:
            raise ValueError('invalid path tracking parameters')
        self.lookahead, self.arrival_radius = lookahead, arrival_radius
        self.slowdown_distance, self.max_magnitude = slowdown_distance, max_magnitude
        self._validated_route_key = None
        self._validated_route = False

    def command(self, position, path, *, walls, confidence=1.):
        if (not path or not isfinite(confidence) or confidence < .5
                or not all(isfinite(v) for p in (position, *path) for v in p)):
            return (0., 0.)
        # A stale/invalid route must trigger replanning, not incremental motion
        # toward a wall just because the first few pixels remain clear.
        route_key = tuple((float(point[0]), float(point[1])) for point in path)
        # Cache only immutable wall maps.  A writable NumPy map may be updated
        # in place by a caller; revalidate it so a newly appeared wall cannot
        # reuse a stale route verdict.
        flags = getattr(walls, "flags", None)
        cacheable_walls = flags is not None and not bool(flags.writeable)
        if not cacheable_walls or route_key != self._validated_route_key:
            self._validated_route_key = route_key
            self._validated_route = all(
                line_is_walkable(walls, a, b, corner_safe=True)
                for a, b in pairwise(path)
            )
        if not self._validated_route:
            return (0., 0.)
        distance = point_distance(position, path[-1])
        if distance <= self.arrival_radius:
            return (0., 0.)
        lengths = build_cumulative_lengths(path)
        projection = project_point_onto_path(position, path, lengths)
        progress = projection['distance']
        # Reduce lookahead at a corner until the direct segment is collision-free.
        for advance in (self.lookahead, self.lookahead/2, 1.):
            target = interpolate_by_distance(path, lengths, progress+advance)
            if not line_is_walkable(walls, position, target, corner_safe=True):
                continue
            dx, dy = target[0]-position[0], target[1]-position[1]
            norm = hypot(dx, dy)
            if norm < 1e-6:
                return (0., 0.)
            magnitude = min(self.max_magnitude, distance/self.slowdown_distance, confidence)
            if advance < self.lookahead:
                magnitude *= .5
            return (dx/norm*magnitude, dy/norm*magnitude)
        return (0., 0.)
