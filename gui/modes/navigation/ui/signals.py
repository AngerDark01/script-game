from __future__ import annotations


def connect_navigation_signals(owner) -> None:
    """Wire navigation UI controls to the owner slots."""
    owner.btn_load.clicked.connect(owner.load_map)
    owner.btn_hint.clicked.connect(owner.toggle_hint_mode)
    owner.btn_start.clicked.connect(owner.toggle_navigation)
    owner.btn_set_exit.clicked.connect(owner.toggle_exit_mode)
    owner.btn_add_required.clicked.connect(owner.toggle_required_mode)
    owner.btn_undo_required.clicked.connect(owner.undo_required_point)
    owner.btn_add_guide.clicked.connect(owner.toggle_guide_mode)
    owner.btn_undo_guide.clicked.connect(owner.undo_guide_point)
    owner.btn_clear_route.clicked.connect(owner.clear_route)
    owner.btn_save_route.clicked.connect(owner.save_route)
    owner.btn_auto_nav.clicked.connect(owner.toggle_auto_navigation)

    owner.params_button.clicked.connect(owner.toggle_params_dialog)
    owner.event_button.clicked.connect(owner.toggle_event_dialog)
    owner.sample_window_button.clicked.connect(owner.toggle_minimap_sample_window)
    owner.save_minimap_sample_button.clicked.connect(owner.save_minimap_sample)
    owner.map_zoom_out_button.clicked.connect(owner.view.zoom_out)
    owner.map_fit_button.clicked.connect(owner.view.fit_map)
    owner.map_zoom_in_button.clicked.connect(owner.view.zoom_in)
    owner.calibrate_button.clicked.connect(owner._calibrate_screen_center)
    owner.compact_mode_button.clicked.connect(owner.navigation_compact_controller.toggle_compact_mode)
    owner.route_tools_button.clicked.connect(owner.navigation_compact_controller.toggle_route_tools)

    owner.params_dialog.parameters_changed.connect(owner._on_parameter_changed)
    owner.params_dialog.save_requested.connect(owner._save_nav_config)
    owner.params_dialog.save_default_requested.connect(owner._save_nav_default_config)
    owner.params_dialog.nav_toggle_overlay_btn.clicked.connect(owner._toggle_overlay_display)
    owner._connect_event_dialog_signals()
