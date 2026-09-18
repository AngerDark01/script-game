from __future__ import annotations

from .presets import DEFAULT_PRESET_NAME, preset_values


def load_params_to_widgets(dialog, params: dict) -> None:
    dialog.blur_strength_spin.setValue(3)
    dialog.deepen_enabled_check.setChecked(params.get("deepen_enabled", True))
    dialog.contrast_factor_spin.setValue(params.get("deepen_factor", 1.2))
    dialog.blue_boost_spin.setValue(params.get("blue_boost", 1.1))

    dialog.gamma_enabled_check.setChecked(params.get("gamma_enabled", True))
    dialog.gamma_value_spin.setValue(params.get("gamma_value", 2.0))

    dialog.tophat_enabled_check.setChecked(params.get("tophat_enabled", True))
    dialog.tophat_kernel_spin.setValue(params.get("tophat_kernel_size", 15))
    dialog.tophat_strength_spin.setValue(params.get("tophat_strength", 4))

    dialog.clahe_enabled_check.setChecked(params.get("clahe_enabled", True))
    dialog.clahe_clip_spin.setValue(params.get("clahe_clip", 2.0))
    dialog.clahe_grid_spin.setValue(params.get("clahe_grid", 8))

    dialog.edge_low_spin.setValue(params.get("edge_low", 50))
    dialog.edge_high_spin.setValue(params.get("edge_high", 150))
    dialog.wall_weight_spin.setValue(params.get("wall_weight", 50))
    dialog.edge_weight_spin.setValue(params.get("edge_weight", 30))
    dialog.gray_weight_spin.setValue(params.get("gray_weight", 20))

    dialog.transparent_mode_check.setChecked(params.get("transparent_mode", False))
    dialog.trans_wall_thresh_spin.setValue(params.get("trans_wall_thresh", 60))
    dialog.trans_sat_penalty_spin.setValue(params.get("trans_sat_penalty", 1.5))

    dialog.sat_filter_check.setChecked(params.get("sat_filter_enabled", True))
    dialog.sat_thresh_spin.setValue(params.get("sat_filter_thresh", 40))
    dialog.sat_radius_spin.setValue(params.get("sat_filter_radius", 0))

    if hasattr(dialog, "conf_thresh_spin"):
        dialog.conf_thresh_spin.setValue(params.get("conf_thresh", 0.30))
        dialog.keyframe_thresh_spin.setValue(params.get("keyframe_thresh", 0.25))
        dialog.weight_add_spin.setValue(params.get("weight_add", 0.3))
        dialog.weight_cap_spin.setValue(params.get("weight_cap", 5.0))


def collect_params_from_widgets(dialog) -> dict:
    return {
        "deepen_enabled": dialog.deepen_enabled_check.isChecked(),
        "deepen_factor": dialog.contrast_factor_spin.value(),
        "blue_boost": dialog.blue_boost_spin.value(),
        "gamma_enabled": dialog.gamma_enabled_check.isChecked(),
        "gamma_value": dialog.gamma_value_spin.value(),
        "tophat_enabled": dialog.tophat_enabled_check.isChecked(),
        "tophat_kernel_size": dialog.tophat_kernel_spin.value(),
        "tophat_strength": dialog.tophat_strength_spin.value(),
        "clahe_enabled": dialog.clahe_enabled_check.isChecked(),
        "clahe_clip": dialog.clahe_clip_spin.value(),
        "clahe_grid": dialog.clahe_grid_spin.value(),
        "edge_low": dialog.edge_low_spin.value(),
        "edge_high": dialog.edge_high_spin.value(),
        "wall_weight": dialog.wall_weight_spin.value(),
        "edge_weight": dialog.edge_weight_spin.value(),
        "gray_weight": dialog.gray_weight_spin.value(),
        "transparent_mode": dialog.transparent_mode_check.isChecked(),
        "trans_wall_thresh": dialog.trans_wall_thresh_spin.value(),
        "trans_sat_penalty": dialog.trans_sat_penalty_spin.value(),
        "sat_filter_enabled": dialog.sat_filter_check.isChecked(),
        "sat_filter_thresh": dialog.sat_thresh_spin.value(),
        "sat_filter_radius": dialog.sat_radius_spin.value(),
        "conf_thresh": dialog.conf_thresh_spin.value() if hasattr(dialog, "conf_thresh_spin") else 0.3,
        "keyframe_thresh": dialog.keyframe_thresh_spin.value() if hasattr(dialog, "keyframe_thresh_spin") else 0.25,
        "weight_add": dialog.weight_add_spin.value() if hasattr(dialog, "weight_add_spin") else 0.3,
        "weight_cap": dialog.weight_cap_spin.value() if hasattr(dialog, "weight_cap_spin") else 5.0,
    }


def reset_widgets_to_default(dialog) -> None:
    dialog.deepen_enabled_check.setChecked(True)
    dialog.contrast_factor_spin.setValue(1.2)
    dialog.blue_boost_spin.setValue(1.1)
    dialog.gamma_enabled_check.setChecked(True)
    dialog.gamma_value_spin.setValue(2.0)
    dialog.tophat_enabled_check.setChecked(True)
    dialog.tophat_kernel_spin.setValue(15)
    dialog.tophat_strength_spin.setValue(4)
    dialog.clahe_enabled_check.setChecked(True)
    dialog.clahe_clip_spin.setValue(2.0)
    dialog.clahe_grid_spin.setValue(8)

    dialog.edge_low_spin.setValue(50)
    dialog.edge_high_spin.setValue(150)
    dialog.wall_weight_spin.setValue(50)
    dialog.edge_weight_spin.setValue(30)
    dialog.gray_weight_spin.setValue(20)

    dialog.sat_filter_check.setChecked(True)
    dialog.sat_thresh_spin.setValue(40)
    dialog.sat_radius_spin.setValue(0)

    dialog.transparent_mode_check.setChecked(False)
    dialog.trans_wall_thresh_spin.setValue(60)
    dialog.trans_sat_penalty_spin.setValue(1.5)

    if hasattr(dialog, "conf_thresh_spin"):
        dialog.conf_thresh_spin.setValue(0.30)
        dialog.keyframe_thresh_spin.setValue(0.25)
        dialog.weight_add_spin.setValue(0.3)
        dialog.weight_cap_spin.setValue(5.0)


def apply_loaded_params_to_widgets(dialog, params: dict) -> None:
    dialog.deepen_enabled_check.setChecked(params.get("deepen_enabled", True))
    dialog.contrast_factor_spin.setValue(params.get("deepen_factor", 1.2))
    dialog.blue_boost_spin.setValue(params.get("blue_boost", 1.1))
    dialog.clahe_enabled_check.setChecked(params.get("clahe_enabled", True))
    dialog.clahe_clip_spin.setValue(params.get("clahe_clip", 2.0))
    dialog.clahe_grid_spin.setValue(params.get("clahe_grid", 8))

    dialog.edge_low_spin.setValue(params.get("edge_low", 50))
    dialog.edge_high_spin.setValue(params.get("edge_high", 150))
    dialog.wall_weight_spin.setValue(params.get("wall_weight", 50))
    dialog.edge_weight_spin.setValue(params.get("edge_weight", 30))
    dialog.gray_weight_spin.setValue(params.get("gray_weight", 20))

    dialog.sat_filter_check.setChecked(params.get("sat_filter_enabled", True))
    dialog.sat_thresh_spin.setValue(params.get("sat_filter_thresh", 40))
    dialog.sat_radius_spin.setValue(params.get("sat_filter_radius", 0))


def apply_preset_to_widgets(dialog, preset: str) -> bool:
    if preset == DEFAULT_PRESET_NAME:
        reset_widgets_to_default(dialog)
        return True

    values = preset_values(preset)
    if values is None:
        return False

    for widget_name, value in values.items():
        getattr(dialog, widget_name).setValue(value)

    return True
