from __future__ import annotations

import ast
import dataclasses
import functools
from typing import Any, Callable

from gui.dialogs.nav_params.field_specs import (
    TEXT_FIELD_SPECS,
    VALUE_FIELD_SPECS,
    ConfigFieldPath,
    config_value,
    resolve_widget,
)
from gui.navigation_params import NavConfig


def value_field_bindings(panel) -> dict[Any, ConfigFieldPath]:
    """Return numeric/boolean widget bindings for NavConfig fields."""
    return {resolve_widget(panel, spec): spec.field_path for spec in VALUE_FIELD_SPECS}


def text_field_bindings(panel) -> dict[Any, ConfigFieldPath]:
    """Return text widget bindings for NavConfig fields."""
    return {resolve_widget(panel, spec): spec.field_path for spec in TEXT_FIELD_SPECS}


def connect_config_bindings(
    panel,
    update_value: Callable[..., None],
    update_text: Callable[..., None],
) -> None:
    """Connect bound widgets to the dialog's update slots."""
    for spec in VALUE_FIELD_SPECS:
        widget = resolve_widget(panel, spec)
        sub_config, attr = spec.field_path
        if spec.writer == "checked":
            handler = functools.partial(update_value, sub_config, attr, to_bool=True)
            widget.stateChanged.connect(handler)
        else:
            handler = functools.partial(update_value, sub_config, attr)
            widget.valueChanged.connect(handler)

    for spec in TEXT_FIELD_SPECS:
        widget = resolve_widget(panel, spec)
        sub_config, attr = spec.field_path
        handler = functools.partial(update_text, sub_config, attr)
        widget.textChanged.connect(handler)


def replace_config_value(
    config: NavConfig,
    sub_config_name: str | None,
    attr_name: str,
    value,
) -> NavConfig:
    """Return a NavConfig copy with one root or nested dataclass field replaced."""
    target_obj = config
    if sub_config_name:
        target_obj = getattr(config, sub_config_name)

    new_sub_config = dataclasses.replace(target_obj, **{attr_name: value})
    if sub_config_name:
        return dataclasses.replace(config, **{sub_config_name: new_sub_config})
    return new_sub_config


def parse_config_text_value(text: str) -> tuple[bool, Any]:
    """Parse text field content as a Python literal, preserving incomplete-input skips."""
    try:
        return True, ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return False, None


def write_config_to_widgets(panel, config: NavConfig) -> None:
    """Write a NavConfig snapshot into an already-created NavParametersDialog panel."""
    for spec in TEXT_FIELD_SPECS:
        resolve_widget(panel, spec).setText(str(config_value(config, spec)))

    for spec in VALUE_FIELD_SPECS:
        widget = resolve_widget(panel, spec)
        value = config_value(config, spec)
        if spec.writer == "checked":
            widget.setChecked(value)
        else:
            widget.setValue(value)

    panel.nav_info_draw_scale.setText(str(config.draw_scale))
    if config.monitor_region:
        region = config.monitor_region
        panel.nav_info_logical_center.setText(
            f"拉框区域: ({region['left']}, {region['top']}) {region['width']}x{region['height']}"
        )
    else:
        panel.nav_info_logical_center.setText(str(config.monitor_logical_center))

    panel.nav_monitor_size_spin.setValue(config.monitor_size)
    panel.nav_movement_scale_factor_spin.setValue(config.movement_scale_factor)
    panel.nav_game_view_map_size_spin.setValue(config.game_view_map_size)
    panel.nav_movement_min_click_radius_spin.setValue(config.movement_min_click_radius)
    panel.nav_movement_max_click_radius_spin.setValue(config.movement_max_click_radius)
    panel.nav_movement_precision_click_max_radius_spin.setValue(
        config.movement_precision_click_max_radius
    )
    panel.nav_auto_click_cooldown_spin.setValue(config.auto_click_cooldown_ms)
    panel.nav_auto_min_target_delta_spin.setValue(config.auto_min_click_target_delta)
    panel.nav_anchor_arrival_radius_spin.setValue(config.anchor_arrival_radius)
    panel.nav_movement_progress_timeout_spin.setValue(config.movement_progress_timeout_ms)
    panel.nav_movement_min_progress_delta_spin.setValue(config.movement_min_progress_delta)
    panel.nav_movement_max_recover_attempts_spin.setValue(config.movement_max_recover_attempts)
    panel.nav_movement_path_deviation_threshold_spin.setValue(
        config.movement_path_deviation_threshold
    )
    panel.nav_event_approach_enabled_chk.setChecked(config.event_approach_enabled)
    panel.nav_event_visible_margin_spin.setValue(config.event_visible_margin)
    panel.nav_event_approach_lookahead_spin.setValue(config.event_approach_lookahead)
    panel.nav_event_approach_click_cooldown_spin.setValue(
        config.event_approach_click_cooldown_ms
    )
    panel.nav_event_stop_radius_spin.setValue(config.event_stop_radius)
    panel.nav_event_settle_ms_spin.setValue(config.event_settle_ms)
    panel.nav_event_stable_frames_spin.setValue(config.event_stable_frames)
    panel.nav_event_max_motion_per_frame_spin.setValue(config.event_max_motion_per_frame)
    panel.nav_bottom_click_guard_spin.setValue(config.bottom_click_guard_pixels)
    panel.nav_wall_erode_iterations_spin.setValue(config.nav_wall_erode_iterations)
    panel.nav_path_start_clear_radius_spin.setValue(config.path_start_clear_radius)
    panel.nav_path_walkable_snap_radius_spin.setValue(config.path_walkable_snap_radius)
    panel.nav_visual_check_interval_spin.setValue(config.coordinate_visual_check_interval_ms)
    panel.nav_visual_check_margin_spin.setValue(config.coordinate_visual_check_margin)
    panel.nav_visual_match_min_conf_spin.setValue(config.coordinate_visual_match_min_confidence)
    panel.nav_visual_mismatch_threshold_spin.setValue(config.coordinate_visual_mismatch_threshold)
    panel.nav_visual_mismatch_frames_spin.setValue(config.coordinate_visual_mismatch_frames)

    if config.game_screen_center:
        panel.nav_screen_center_x.setText(str(config.game_screen_center[0]))
        panel.nav_screen_center_y.setText(str(config.game_screen_center[1]))
    else:
        panel.nav_screen_center_x.setText("N/A")
        panel.nav_screen_center_y.setText("N/A")

    panel.nav_fps_spin.setValue(config.fps)
