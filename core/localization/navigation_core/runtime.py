from __future__ import annotations

from core.localization.localize_pipeline import localize_frame
from core.localization.map_package import load_navigation_map_package
from core.localization.rendering import render_navigation_map
from core.localization.visual_check import visual_check_position
from core.vision.hsv_recognizer import HSVRecognizer
from core.vision.phase_displacement import estimate_phase_displacement

from .diagnostics import log_template_match_failure
from .registration import (
    clear_navigation_frame_registration,
    set_navigation_frame_registration,
)
from .relocalization import (
    is_full_map_localization,
    request_full_map_localization,
    set_initial_hint,
    template_match_required_confidence,
)
from .state import (
    initialize_map_configuration,
    initialize_runtime_state,
    require_map_data_file,
)
from .wall_layer import (
    navigation_wall_close_kernel,
    rebuild_navigation_wall_layer,
    standardize_navigation_wall_template,
)


class NavigationCore:
    """Stateful navigation localization facade."""

    def __init__(self, map_folder_path, center_offset_y=0, nav_wall_erode_iterations=1):
        initialize_map_configuration(
            self,
            map_folder_path,
            center_offset_y=center_offset_y,
            nav_wall_erode_iterations=nav_wall_erode_iterations,
        )
        require_map_data_file(self)
        self._load_map_data()
        self.recognizer = HSVRecognizer()
        initialize_runtime_state(self)

    def _clear_frame_registration(self, confidence=0.0, source="failed"):
        clear_navigation_frame_registration(self, confidence, source)

    def _set_frame_registration(
        self,
        player_global_pos,
        player_local_pos,
        frame_shape,
        confidence,
        source,
        metadata=None,
    ):
        set_navigation_frame_registration(
            self,
            player_global_pos,
            player_local_pos,
            frame_shape,
            confidence,
            source,
            metadata,
        )

    def set_center_offset(self, center_offset_y):
        self.center_offset_y = center_offset_y
        print(f"NavigationCore center_offset_y updated to: {center_offset_y}")

    def _load_map_data(self):
        load_navigation_map_package(self)

    def rebuild_navigation_wall_layer(self, *, erode_iterations=None) -> None:
        rebuild_navigation_wall_layer(self, erode_iterations=erode_iterations)

    def set_initial_hint(self, pos):
        set_initial_hint(self, pos)

    def request_full_map_localization(self, reason: str = ""):
        request_full_map_localization(self, reason)

    def request_global_relocalization(self, reason: str = ""):
        self.request_full_map_localization(reason)

    def _is_full_map_localization(self, force_global: bool) -> bool:
        return is_full_map_localization(self, force_global)

    def _template_match_required_confidence(self, *, full_map: bool) -> float:
        return template_match_required_confidence(self, full_map=full_map)

    def _estimate_displacement(self, img1, img2):
        return estimate_phase_displacement(img1, img2)

    def _wall_close_kernel(self):
        return navigation_wall_close_kernel(self)

    def _standardize_wall_template(self, wall_mask_scaled):
        return standardize_navigation_wall_template(self, wall_mask_scaled)

    def _log_template_match_failure(
        self,
        *,
        max_val,
        required_conf,
        full_map_localization,
        force_global,
        force_global_reason,
        wall_mask,
        wall_mask_scaled,
        search_area,
        wall_feature_count,
    ):
        log_template_match_failure(
            self,
            max_val=max_val,
            required_conf=required_conf,
            full_map_localization=full_map_localization,
            force_global=force_global,
            force_global_reason=force_global_reason,
            wall_mask=wall_mask,
            wall_mask_scaled=wall_mask_scaled,
            search_area=search_area,
            wall_feature_count=wall_feature_count,
        )

    def _visual_check_position(self, wall_mask, player_pos, expected_player_global_pos):
        return visual_check_position(self, wall_mask, player_pos, expected_player_global_pos)

    def localize(self, minimap_img, player_pos=None):
        return localize_frame(self, minimap_img, player_pos=player_pos)

    def get_map_image(self):
        return render_navigation_map(self)
