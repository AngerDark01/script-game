from __future__ import annotations

import os

from core.shared.frame_registration import FrameRegistration


def initialize_map_configuration(
    nav_core,
    map_folder_path,
    center_offset_y=0,
    nav_wall_erode_iterations=1,
) -> None:
    """Initialize path and map-scale state before map package loading."""
    nav_core.map_folder = map_folder_path
    nav_core.map_data_path = os.path.join(map_folder_path, "map_data.npz")
    nav_core.center_offset_y = center_offset_y
    nav_core.nav_wall_erode_iterations = max(0, int(nav_wall_erode_iterations))
    nav_core.draw_scale = 2.0
    nav_core.map_draw_scale = nav_core.draw_scale
    nav_core.wall_match_close_kernel_size = 3
    nav_core.map_wall_match_close_kernel_size = nav_core.wall_match_close_kernel_size
    nav_core.last_frame_registration = FrameRegistration(
        valid=False,
        draw_scale=nav_core.draw_scale,
    )
    nav_core._last_template_fail_log_ms = 0


def require_map_data_file(nav_core) -> None:
    """Raise if the configured map package is absent."""
    if not os.path.exists(nav_core.map_data_path):
        raise FileNotFoundError(f"Map data not found at: {nav_core.map_data_path}")


def initialize_runtime_state(nav_core) -> None:
    """Initialize localization runtime fields after map package loading.

    The ordering intentionally preserves the public NavigationCore constructor:
    map package fields are loaded first, then runtime tracking fields are reset.
    """
    drawing_saved_pos = getattr(nav_core, "drawing_saved_pos", None)
    nav_core.current_pos = None
    nav_core.drawing_saved_pos = drawing_saved_pos
    nav_core.last_good_pos = None
    if not hasattr(nav_core, "last_pos"):
        nav_core.last_pos = drawing_saved_pos
    nav_core.is_localized = False
    nav_core.is_first_frame_localized = False

    nav_core.search_radius = 200
    nav_core.confidence_threshold = 0.6
    nav_core.crop_offset = (0, 0)

    nav_core.prev_mask = None
    nav_core.prev_wall_mask = None
    nav_core.last_player_local_pos = None

    nav_core.min_match_features = 80
    nav_core.min_wall_features = 50
    nav_core.f2f_confidence_threshold = 0.35
    nav_core.f2f_max_shift = 70.0
    nav_core.relocalize_confidence_threshold = 0.72
    nav_core.relocalize_max_jump = 220.0
    nav_core.local_search_radius = 800
    nav_core.force_global_relocalization = False
    nav_core.force_global_relocalization_reason = ""
    nav_core.visual_check_interval_ms = 800
    nav_core.visual_check_margin = 140
    nav_core.visual_check_min_confidence = 0.72
    nav_core.visual_mismatch_threshold = 24.0
    nav_core._last_visual_check_ms = 0

    nav_core.manual_offset = (0, 0)
