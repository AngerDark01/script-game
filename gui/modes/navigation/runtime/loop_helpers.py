from __future__ import annotations


def should_run_navigation_tasks(*, auto_navigation_enabled: bool, manual_event_test_active: bool) -> bool:
    return bool(auto_navigation_enabled or manual_event_test_active)


def compute_navigation_lookahead(*, capture_width: int, draw_scale: float) -> float:
    return max(36.0, min(float(capture_width) * float(draw_scale) * 0.18, 120.0))
