from __future__ import annotations


def float_point(point) -> tuple[float, float]:
    return (float(point[0]), float(point[1]))


def int_point(point) -> tuple[int, int]:
    return (int(round(float(point[0]))), int(round(float(point[1]))))
