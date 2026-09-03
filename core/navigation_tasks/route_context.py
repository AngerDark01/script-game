from __future__ import annotations

from core.routing.geometry import point_distance
from core.routing.route_progress import build_cumulative_lengths, project_point_on_polyline

from .models import RouteAnchor, RouteProjection


class RouteContext:
    """Polyline projection helper for user-authored guide anchors."""

    def __init__(self, guide_points=None):
        self.anchors: list[RouteAnchor] = []
        self._points = _dedupe_points(guide_points or [])
        self._cumulative = self._build_cumulative(self._points)
        for index, point in enumerate(self._points):
            progress = self._cumulative[index] if index < len(self._cumulative) else 0.0
            self.anchors.append(RouteAnchor(index=index, point=point, progress=float(progress)))

    @property
    def points(self) -> list[tuple[float, float]]:
        return list(self._points)

    def has_route(self) -> bool:
        return len(self._points) >= 2

    def project(self, point) -> RouteProjection | None:
        projection = project_point_on_polyline(
            point,
            self._points,
            self._cumulative,
            degenerate_epsilon=1e-6,
        )
        if projection is None:
            return None
        return RouteProjection(
            point=projection.point,
            progress=projection.progress,
            segment_index=projection.segment_index,
            deviation=projection.deviation,
        )

    def progress_of(self, point) -> float | None:
        projection = self.project(point)
        return None if projection is None else float(projection.progress)

    def anchor_at(self, index: int) -> RouteAnchor | None:
        if index < 0 or index >= len(self.anchors):
            return None
        return self.anchors[index]

    def consumed_index_for_position(self, point, reached_radius: float = 26.0) -> int:
        if not self.anchors:
            return -1
        projection = self.project(point)
        if projection is None:
            return -1
        consumed = -1
        radius = max(1.0, float(reached_radius))
        for anchor in self.anchors:
            if anchor.progress < projection.progress - radius:
                consumed = anchor.index
                continue
            if point_distance(point, anchor.point) <= radius:
                consumed = max(consumed, anchor.index)
        return consumed

    def corridor_anchors(
        self,
        current_pos,
        target_pos,
        *,
        reached_radius: float = 26.0,
        target_margin: float = 36.0,
        max_anchors: int = 48,
    ) -> list[tuple[float, float]]:
        if not self.anchors:
            return []

        current_projection = self.project(current_pos)
        target_projection = self.project(target_pos)
        if current_projection is None or target_projection is None:
            return []
        if target_projection.progress <= current_projection.progress + max(4.0, float(reached_radius) * 0.5):
            return []

        result: list[tuple[float, float]] = []
        lower = current_projection.progress + max(4.0, float(reached_radius) * 0.5)
        upper = target_projection.progress + max(float(target_margin), float(reached_radius))
        for anchor in self.anchors:
            if anchor.progress < lower:
                continue
            if point_distance(current_pos, anchor.point) <= float(reached_radius):
                continue
            if anchor.progress > upper:
                continue
            result.append(anchor.point)
            if len(result) >= int(max_anchors):
                break
        return result

    def next_anchor(
        self,
        current_pos,
        target_pos,
        consumed_anchor_index: int = -1,
        reached_radius: float = 26.0,
    ) -> RouteAnchor | None:
        candidates = self.corridor_anchors(
            current_pos,
            target_pos,
            reached_radius=reached_radius,
            max_anchors=1,
        )
        if not candidates:
            return None
        point = candidates[0]
        for anchor in self.anchors:
            if anchor.index <= int(consumed_anchor_index):
                continue
            if point_distance(anchor.point, point) <= 1e-6:
                return anchor
        return None

    @staticmethod
    def _build_cumulative(points: list[tuple[float, float]]) -> list[float]:
        return build_cumulative_lengths(points)


def _dedupe_points(points) -> list[tuple[float, float]]:
    result: list[tuple[float, float]] = []
    seen: set[tuple[int, int]] = set()
    for raw in points:
        if raw is None or len(raw) < 2:
            continue
        key = (int(round(float(raw[0]))), int(round(float(raw[1]))))
        if key in seen:
            continue
        seen.add(key)
        result.append((float(raw[0]), float(raw[1])))
    return result
