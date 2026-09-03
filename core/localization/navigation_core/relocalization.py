from __future__ import annotations


def set_initial_hint(nav_core, pos) -> None:
    """Seed localization with a known map coordinate and reset F2F tracking."""
    nav_core.current_pos = pos
    nav_core.last_good_pos = pos
    nav_core.is_localized = True
    nav_core.prev_mask = None
    nav_core.prev_wall_mask = None
    nav_core._last_visual_check_ms = 0

    print(f"Initial hint set to: {pos}. Waiting for next frame to snap.")


def request_full_map_localization(nav_core, reason: str = "") -> None:
    """Force the next frame through the full-map template match path."""
    nav_core.force_global_relocalization = True
    nav_core.force_global_relocalization_reason = str(reason or "coordinate_recovery")
    nav_core.is_localized = False
    nav_core.prev_mask = None
    nav_core.prev_wall_mask = None
    nav_core._last_visual_check_ms = 0


def is_full_map_localization(nav_core, force_global: bool) -> bool:
    """Return whether this frame must search the complete map layer."""
    return bool(force_global) or not (
        nav_core.is_localized and nav_core.current_pos is not None
    )


def template_match_required_confidence(nav_core, *, full_map: bool) -> float:
    """Return the acceptance threshold for current template-match mode."""
    if full_map:
        return float(nav_core.confidence_threshold)
    required_conf = float(nav_core.confidence_threshold)
    if nav_core.last_good_pos is not None:
        required_conf = max(required_conf, float(nav_core.relocalize_confidence_threshold))
    return required_conf
