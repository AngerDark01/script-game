import time

from core.foundation.clock import MonotonicClock
from core.foundation.geometry import Point2, Transform2D, Vector2


def test_point_vector_and_distance_operations():
    point = Point2(10, 20)
    delta = Vector2(3, -4)
    assert point + delta == Point2(13, 16)
    assert point - Point2(7, 16) == Vector2(3, 4)
    assert delta.length() == 5
    assert point.distance_to(Point2(13, 24)) == 5


def test_transform_applies_scale_then_translation():
    transform = Transform2D(scale=2.0, offset=Vector2(100, 50))
    assert transform.apply(Point2(3, 4)) == Point2(106, 58)


def test_monotonic_clock_never_moves_backwards():
    clock = MonotonicClock()
    first = clock.now()
    time.sleep(0.001)
    second = clock.now()
    assert second >= first
