"""Bounded local visual reacquisition helpers."""

from __future__ import annotations


def roi_radii() -> tuple[float, float, float]:
    return (80.0, 140.0, 220.0)


def accept_local_score(score: float, *, threshold: float = 0.55) -> bool:
    return float(score) >= float(threshold)


__all__ = ["accept_local_score", "roi_radii"]
