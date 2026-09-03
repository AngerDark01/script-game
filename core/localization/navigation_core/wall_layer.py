from __future__ import annotations

from core.localization.frame_matcher import (
    standardize_wall_template,
    wall_close_kernel,
)
from core.routing.obstacles import derive_navigation_wall_layer


def rebuild_navigation_wall_layer(nav_core, *, erode_iterations=None) -> None:
    """Refresh the A*-only wall layer derived from the localization wall layer."""
    if erode_iterations is not None:
        nav_core.nav_wall_erode_iterations = max(0, int(erode_iterations))
    nav_core.nav_wall_layer = derive_navigation_wall_layer(
        nav_core.wall_layer,
        erode_iterations=nav_core.nav_wall_erode_iterations,
    )


def navigation_wall_close_kernel(nav_core):
    """Return the wall-template close kernel configured on the NavigationCore."""
    return wall_close_kernel(getattr(nav_core, "wall_match_close_kernel_size", 3))


def standardize_navigation_wall_template(nav_core, wall_mask_scaled):
    """Normalize wall-template thickness using the NavigationCore kernel setting."""
    return standardize_wall_template(
        wall_mask_scaled,
        getattr(nav_core, "wall_match_close_kernel_size", 3),
    )
