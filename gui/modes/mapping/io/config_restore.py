"""Restore saved mapping config into runtime services and controls."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSignalBlocker

from gui.modes.mapping.params.binding import (
    sync_geometry_widgets,
    sync_recognizer_widgets,
    sync_stitcher_widgets,
)

from .config_store import load_root_config


@dataclass(frozen=True)
class MappingConfigRestoreTargets:
    size_spin: object
    fps_spin: object
    clahe_check: object
    deepen_check: object
    wall_weight_spin: object
    edge_weight_spin: object
    gray_weight_spin: object
    canny_low_spin: object
    canny_high_spin: object
    weight_spin: object
    draw_scale_spin: object
    canvas_size_spin: object
    player_clear_radius_spin: object
    wall_close_kernel_spin: object


def restore_saved_mapping_config(
    file_path,
    *,
    app_context,
    capture_selection,
    handle_capture_selection_result,
    stitcher_is_empty,
    targets: MappingConfigRestoreTargets,
) -> bool:
    """Load root config and apply it to mapping runtime state and controls."""
    config = load_root_config(file_path)
    if config is None:
        return False

    app_context.monitor_logical_center = config.get("monitor_logical_center")
    app_context.monitor_size = config.get("monitor_size", 320)
    app_context.monitor_region = config.get("monitor_region")

    selection_result = capture_selection.restore_from_context()
    if selection_result is not None:
        handle_capture_selection_result(selection_result, save=False)

    targets.size_spin.setValue(app_context.monitor_size)
    targets.fps_spin.setValue(config.get("fps", 10))

    recognizer_params = config.get("recognizer_params")
    if recognizer_params is not None:
        app_context.recognizer.set_params(recognizer_params)
        sync_recognizer_widgets(
            recognizer_params,
            clahe_check=targets.clahe_check,
            deepen_check=targets.deepen_check,
            wall_weight_spin=targets.wall_weight_spin,
            edge_weight_spin=targets.edge_weight_spin,
            gray_weight_spin=targets.gray_weight_spin,
            canny_low_spin=targets.canny_low_spin,
            canny_high_spin=targets.canny_high_spin,
        )

    stitcher_params = config.get("stitcher_params")
    if stitcher_params is not None:
        if stitcher_is_empty():
            app_context.stitcher.reinitialize_canvas(
                canvas_size=stitcher_params.get("canvas_size", app_context.stitcher.canvas_size),
                draw_scale=stitcher_params.get("draw_scale", app_context.stitcher.draw_scale),
                wall_close_kernel_size=stitcher_params.get(
                    "wall_close_kernel_size",
                    getattr(app_context.stitcher, "wall_close_kernel_size", 3),
                ),
            )
        app_context.stitcher.set_params(stitcher_params)
        sync_stitcher_widgets(stitcher_params, weight_spin=targets.weight_spin)

    blockers = [
        QSignalBlocker(targets.draw_scale_spin),
        QSignalBlocker(targets.canvas_size_spin),
        QSignalBlocker(targets.player_clear_radius_spin),
        QSignalBlocker(targets.wall_close_kernel_spin),
    ]
    try:
        sync_geometry_widgets(
            config.get("recognizer_params", {}),
            config.get("stitcher_params", {}),
            draw_scale_spin=targets.draw_scale_spin,
            canvas_size_spin=targets.canvas_size_spin,
            player_clear_radius_spin=targets.player_clear_radius_spin,
            wall_close_kernel_spin=targets.wall_close_kernel_spin,
        )
    finally:
        del blockers

    return True
