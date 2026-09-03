"""Widget-to-parameter binding helpers for mapping mode."""

from __future__ import annotations


def apply_hsv_toggles(recognizer, wall_check, fog_check) -> None:
    recognizer.enable_wall = wall_check.isChecked()
    recognizer.enable_fog = fog_check.isChecked()


def feature_params_from_widgets(
    *,
    clahe_check,
    deepen_check,
    wall_weight_spin,
    edge_weight_spin,
    gray_weight_spin,
    canny_low_spin,
    canny_high_spin,
) -> dict:
    return {
        "clahe_enabled": clahe_check.isChecked(),
        "deepen_enabled": deepen_check.isChecked(),
        "wall_weight": wall_weight_spin.value(),
        "edge_weight": edge_weight_spin.value(),
        "gray_weight": gray_weight_spin.value(),
        "edge_low": canny_low_spin.value(),
        "edge_high": canny_high_spin.value(),
    }


def apply_merge_weight(stitcher, weight_spin) -> None:
    stitcher.weight_add = weight_spin.value()


def sync_recognizer_widgets(
    params: dict,
    *,
    clahe_check,
    deepen_check,
    wall_weight_spin,
    edge_weight_spin,
    gray_weight_spin,
    canny_low_spin,
    canny_high_spin,
) -> None:
    clahe_check.setChecked(params.get("clahe_enabled", True))
    deepen_check.setChecked(params.get("deepen_enabled", True))
    wall_weight_spin.setValue(params.get("wall_weight", 50))
    edge_weight_spin.setValue(params.get("edge_weight", 30))
    gray_weight_spin.setValue(params.get("gray_weight", 20))
    canny_low_spin.setValue(params.get("edge_low", 50))
    canny_high_spin.setValue(params.get("edge_high", 150))


def sync_stitcher_widgets(params: dict, *, weight_spin) -> None:
    weight_spin.setValue(params.get("weight_add", 0.3))


def sync_geometry_widgets(
    recognizer_params: dict,
    stitcher_params: dict,
    *,
    draw_scale_spin,
    canvas_size_spin,
    player_clear_radius_spin,
    wall_close_kernel_spin,
) -> None:
    draw_scale_spin.setValue(float(stitcher_params.get("draw_scale", 2.0)))
    canvas_size_spin.setValue(int(stitcher_params.get("canvas_size", 5000)))
    player_clear_radius_spin.setValue(int(recognizer_params.get("player_clear_radius", 22)))
    wall_close_kernel_spin.setValue(int(stitcher_params.get("wall_close_kernel_size", 3)))
