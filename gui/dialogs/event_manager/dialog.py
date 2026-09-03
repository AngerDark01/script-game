from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QSignalBlocker
from PySide6.QtWidgets import QDialog

from core.events.config import build_tui_event_options

from .layout import COMPACT_PARAM_KEYS, build_event_manager_ui
from .schema_form import (
    clear_param_form,
    create_param_label,
    create_param_widget,
    editable_schema_items,
    sync_param_widget_maps,
)
from .task_table import render_task_rows


class EventManagerDialog(QDialog):
    """Non-modal UI for complete event-package enablement and live task state."""

    config_changed = Signal(object)
    save_requested = Signal()
    test_portal_requested = Signal()
    reset_portal_requested = Signal()
    reset_events_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("事件管理")
        self.setModal(False)
        self.setWindowFlags(self.windowFlags() | Qt.Tool)
        self.setAttribute(Qt.WA_DeleteOnClose, False)

        self.registry = None
        self.config = None
        self.coordinator = None
        self.map_name = ""
        self._event_options: list[dict] = []
        self._param_widgets: dict[str, object] = {}
        self._compact_param_widgets: dict[str, object] = {}
        self._selected_event_type: str | None = None
        self._compact_mode = True
        self._syncing_params = False
        self._syncing_event_controls = False

        build_event_manager_ui(self)
        self.set_compact_mode(True, resize_window=False)
        self.resize(860, 760)

    def set_context(self, registry, config, coordinator=None, map_name: str = "") -> None:
        self.registry = registry
        self.config = config
        self.coordinator = coordinator
        self.map_name = map_name or ""
        self.refresh()

    def refresh(self) -> None:
        self._refresh_events()
        self._refresh_tasks()
        self._refresh_hooks()

    def refresh_tasks(self) -> None:
        self._refresh_tasks()

    def set_compact_mode(self, compact: bool, *, resize_window: bool = True) -> None:
        self._compact_mode = bool(compact)
        page = self.compact_page if self._compact_mode else self.full_page
        self.content_stack.setCurrentWidget(page)
        self.compact_mode_button.setText("完整模式" if self._compact_mode else "小窗模式")
        if self._compact_mode:
            self.setMinimumSize(760, 560)
            if resize_window:
                self.resize(860, 760)
            return
        self.setMinimumSize(880, 620)
        if resize_window:
            self.resize(1040, 780)

    def _toggle_compact_mode(self) -> None:
        self.set_compact_mode(not self._compact_mode)

    def _refresh_events(self) -> None:
        previous_selection = self._selected_event_type
        self._event_options = []
        self.map_label.setText(f"地图: {self.map_name or '-'}")
        self._syncing_event_controls = True
        self.event_selector.clear()
        self.selected_event_enabled_checkbox.setChecked(False)
        self.selected_event_enabled_checkbox.setEnabled(False)
        self._set_event_text("选择一个事件后可调整参数。", "")
        self._syncing_event_controls = False

        if not self.registry or not self.config:
            self.global_enabled_checkbox.setEnabled(False)
            self.reset_portal_button.setEnabled(False)
            self.test_portal_button.setEnabled(False)
            self.event_selector.setEnabled(False)
            self.status_label.setText("未加载事件配置")
            self._clear_params("请先加载地图。")
            return

        self.global_enabled_checkbox.setEnabled(True)
        self.reset_portal_button.setEnabled(True)
        self.test_portal_button.setEnabled(True)
        self.event_selector.setEnabled(True)
        with QSignalBlocker(self.global_enabled_checkbox):
            self.global_enabled_checkbox.setChecked(bool(getattr(self.config, "enabled", True)))

        self._event_options = build_tui_event_options(self.registry, self.config)
        self._populate_event_selector(previous_selection)
        self._restore_event_selection(previous_selection)
        self.status_label.setText(f"{len(self._event_options)} 个完整事件，{len(self._current_tasks())} 个已识别任务")

    def _refresh_tasks(self) -> None:
        tasks = self._current_tasks()
        render_task_rows(self.task_table, tasks)
        render_task_rows(self.compact_task_table, tasks, compact=True)
        if self.config:
            self.status_label.setText(
                f"{len(build_tui_event_options(self.registry, self.config)) if self.registry else 0} "
                f"个完整事件，{len(tasks)} 个已识别任务"
            )

    def _current_tasks(self) -> list:
        if not self.coordinator:
            return []
        try:
            return self.coordinator.tasks()
        except Exception:
            return []

    def _on_global_enabled_changed(self, *_args) -> None:
        if not self.config:
            return
        self.config.enabled = bool(self.global_enabled_checkbox.isChecked())
        self.config_changed.emit(self.config)
        self.refresh()

    def _on_event_enabled_changed(self, event_type: str) -> None:
        if not self.config:
            return
        event_config = self.config.events.setdefault(event_type, {})
        event_config["enabled"] = bool(self.selected_event_enabled_checkbox.isChecked())
        self.config_changed.emit(self.config)
        self.refresh()

    def _refresh_hooks(self) -> None:
        self.hook_panel.set_config(self.config, self._event_options)

    def _on_hooks_changed(self) -> None:
        if not self.config:
            return
        self.config_changed.emit(self.config)

    def _on_event_selection_changed(self) -> None:
        if self._syncing_event_controls:
            return
        row = self.event_selector.currentIndex()
        if row < 0 or row >= len(self._event_options):
            self._selected_event_type = None
            self._clear_params("选择一个事件后可调整参数。")
            self._set_event_text("选择一个事件后可调整参数。", "")
            self.selected_event_enabled_checkbox.setEnabled(False)
            return
        option = self._event_options[row]
        self._selected_event_type = str(option.get("event_type", ""))
        self._sync_selected_event_controls(option)
        self._render_params(option)

    def _on_selected_event_enabled_changed(self, *_args) -> None:
        if self._syncing_event_controls or not self._selected_event_type:
            return
        self._on_event_enabled_changed(self._selected_event_type)

    def _populate_event_selector(self, selected_event_type: str | None) -> None:
        target_index = 0
        self._syncing_event_controls = True
        try:
            self.event_selector.clear()
            for row, option in enumerate(self._event_options):
                event_type = str(option.get("event_type") or "")
                display_name = str(option.get("display_name") or event_type)
                priority = option.get("current_values", {}).get("priority", "")
                enabled = bool(option.get("enabled", True))
                label = f"{display_name} ({event_type}) - 优先级 {priority}"
                if not enabled:
                    label += " - 已关闭"
                self.event_selector.addItem(label, event_type)
                if selected_event_type and event_type == selected_event_type:
                    target_index = row
            if self._event_options:
                self.event_selector.setCurrentIndex(target_index)
        finally:
            self._syncing_event_controls = False

    def _restore_event_selection(self, event_type: str | None) -> None:
        if not self._event_options:
            self._selected_event_type = None
            self._clear_params("没有可配置事件。")
            self._set_event_text("没有可配置事件。", "")
            self.selected_event_enabled_checkbox.setEnabled(False)
            return
        target_row = 0
        if event_type:
            for row, option in enumerate(self._event_options):
                if str(option.get("event_type", "")) == event_type:
                    target_row = row
                    break
        with QSignalBlocker(self.event_selector):
            self.event_selector.setCurrentIndex(target_row)
        self._selected_event_type = str(self._event_options[target_row].get("event_type", ""))
        self._sync_selected_event_controls(self._event_options[target_row])
        self._render_params(self._event_options[target_row])

    def _sync_selected_event_controls(self, option: dict) -> None:
        values = option.get("current_values", {}) or {}
        self._syncing_event_controls = True
        try:
            self.selected_event_enabled_checkbox.setEnabled(True)
            self.selected_event_enabled_checkbox.setChecked(bool(values.get("enabled", option.get("enabled", True))))
            self._set_event_text(
                str(option.get("description") or ""),
                self._format_current_values(values),
            )
        finally:
            self._syncing_event_controls = False

    def _set_event_text(self, description: str, summary: str) -> None:
        self.event_description_label.setText(description)
        self.compact_event_description_label.setText(description)
        self.event_summary_label.setText(summary)
        self.compact_event_summary_label.setText(summary)

    def _clear_params(self, message: str = "") -> None:
        clear_param_form(self.params_layout, self._param_widgets, message)
        clear_param_form(self.compact_params_layout, self._compact_param_widgets, message)

    def _render_params(self, option: dict) -> None:
        schema = option.get("schema", {}) or {}
        event_type = str(option.get("event_type", ""))
        values = self.config.events.setdefault(event_type, {}) if self.config else {}
        editable_items = editable_schema_items(schema)
        compact_items = editable_schema_items(schema, COMPACT_PARAM_KEYS)
        clear_param_form(self.params_layout, self._param_widgets, "")
        clear_param_form(self.compact_params_layout, self._compact_param_widgets, "")
        if not editable_items:
            clear_param_form(self.params_layout, self._param_widgets, "该事件没有可编辑参数。")
            clear_param_form(self.compact_params_layout, self._compact_param_widgets, "该事件没有可编辑参数。")
            return

        self._syncing_params = True
        try:
            self._render_param_items(self.params_layout, self._param_widgets, editable_items, values)
            if compact_items:
                self._render_param_items(self.compact_params_layout, self._compact_param_widgets, compact_items, values)
            else:
                clear_param_form(
                    self.compact_params_layout,
                    self._compact_param_widgets,
                    "该事件没有常用参数，请切换完整模式。",
                )
        finally:
            self._syncing_params = False

    def _render_param_items(self, layout, widgets: dict[str, object], items: list[tuple[str, dict]], values: dict) -> None:
        for key, spec in items:
            widget = create_param_widget(key, spec, values.get(key), self._on_param_changed)
            tooltip = str(spec.get("help") or "")
            if tooltip and hasattr(widget, "setToolTip"):
                widget.setToolTip(tooltip)
            widgets[key] = widget
            layout.addRow(create_param_label(key, spec), widget)

    def _on_param_changed(self, key: str, value) -> None:
        if self._syncing_params or not self.config or not self._selected_event_type:
            return
        event_config = self.config.events.setdefault(self._selected_event_type, {})
        event_config[key] = value
        self.config_changed.emit(self.config)
        sync_param_widget_maps(
            (self._param_widgets, self._compact_param_widgets),
            key,
            value,
            self._schema_spec_for_key(key),
        )
        self._update_event_summary(self._selected_event_type)

    def _schema_spec_for_key(self, key: str) -> dict | None:
        for option in self._event_options:
            if str(option.get("event_type", "")) == self._selected_event_type:
                schema = option.get("schema", {}) or {}
                spec = schema.get(key)
                return spec if isinstance(spec, dict) else None
        return None

    def _update_event_summary(self, event_type: str) -> None:
        if not self.config:
            return
        for option in self._event_options:
            if str(option.get("event_type", "")) != event_type:
                continue
            values = self.config.events.get(event_type, {})
            option["current_values"] = values
            if event_type == self._selected_event_type:
                self._set_event_text(
                    str(option.get("description") or ""),
                    self._format_current_values(values),
                )
                self._syncing_event_controls = True
                try:
                    self.selected_event_enabled_checkbox.setChecked(bool(values.get("enabled", option.get("enabled", True))))
                finally:
                    self._syncing_event_controls = False
            break

    def _format_current_values(self, values: dict) -> str:
        keys = [
            "interaction",
            "detector_mode",
            "minimap_threshold",
            "max_candidates",
            "minimap_nms_radius",
            "min_blue_ratio",
            "feature_sat_min",
            "feature_val_min",
            "feature_min_blue_pixels",
            "shape_min_outer_score",
            "shape_min_shape_score",
            "shape_signature_min_edge_score",
            "shape_signature_min_color_score",
            "stable_frames",
            "arrival_radius",
            "interact_radius",
            "portal_point_click_wait_ms",
            "weighted_threshold",
            "detection_interval_ms",
            "roi_prefilter_enabled",
            "roi_expand",
            "template_weight",
            "shape_weight",
            "color_weight",
            "target_update_mode",
            "target_update_max_drift",
            "player_marker_exclusion_enabled",
            "player_center_mask_enabled",
            "player_center_mask_overlay_enabled",
            "player_center_mask_radius",
            "scales",
            "stable_frames",
            "localization_cluster_radius",
            "stable_variance",
            "dedupe_radius",
            "localization_max_samples",
            "localization_cluster_ttl_ms",
            "localization_emit_interval_ms",
            "memory_confirm_frames",
            "max_blobs_per_frame",
            "pickup_radius",
            "pickup_key",
            "post_pickup_wait_ms",
            "absence_confirm_frames",
            "absence_frame_ms",
            "pickup_press_limit",
            "cooldown_ms",
            "cooldown_radius",
            "type_cooldown_ms",
            "retry_limit",
            "diagnostic_capture_enabled",
            "diagnostic_capture_interval_ms",
            "diagnostic_capture_max_frames",
        ]
        parts = []
        for key in keys:
            if key in values:
                parts.append(f"{key}={values[key]}")
        return ", ".join(parts)
