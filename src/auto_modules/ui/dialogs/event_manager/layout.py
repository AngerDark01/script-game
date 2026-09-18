from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTabWidget,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from .hooks import EventHookPanel
from .task_table import configure_task_table


COMPACT_PARAM_KEYS = (
    "navigation_approach_enabled",
    "detector_mode",
    "minimap_threshold",
    "max_candidates",
    "minimap_nms_radius",
    "weighted_threshold",
    "template_weight",
    "shape_weight",
    "color_weight",
    "player_center_mask_enabled",
    "player_center_mask_radius",
    "pickup_radius",
    "pickup_key",
    "diagnostic_capture_enabled",
    "diagnostic_capture_interval_ms",
    "localization_cluster_radius",
    "dedupe_radius",
    "target_update_mode",
    "target_update_max_drift",
    "player_center_mask_overlay_enabled",
)


def build_event_manager_ui(dialog) -> None:
    """Build the event manager dialog shell and attach expected attributes."""
    layout = QVBoxLayout(dialog)

    header = QVBoxLayout()
    top_row = QHBoxLayout()
    dialog.map_label = QLabel("地图: -")
    dialog.global_enabled_checkbox = QCheckBox("启用事件系统")
    dialog.compact_mode_button = QPushButton("完整模式")
    dialog.compact_mode_button.setToolTip("在小窗和完整事件管理界面之间切换")
    top_row.addWidget(dialog.map_label, 1)
    top_row.addWidget(dialog.global_enabled_checkbox)
    top_row.addWidget(dialog.compact_mode_button)
    header.addLayout(top_row)

    event_row = QHBoxLayout()
    event_row.addWidget(QLabel("当前事件"))
    dialog.event_selector = QComboBox()
    dialog.selected_event_enabled_checkbox = QCheckBox("启用当前事件")
    event_row.addWidget(dialog.event_selector, 1)
    event_row.addWidget(dialog.selected_event_enabled_checkbox)
    header.addLayout(event_row)
    layout.addLayout(header)

    dialog.content_stack = QStackedWidget()
    dialog.full_page = _build_full_page(dialog)
    dialog.compact_page = _build_compact_page(dialog)
    dialog.content_stack.addWidget(dialog.compact_page)
    dialog.content_stack.addWidget(dialog.full_page)
    layout.addWidget(dialog.content_stack, 1)

    _build_footer(dialog, layout)

    dialog.global_enabled_checkbox.stateChanged.connect(dialog._on_global_enabled_changed)
    dialog.event_selector.currentIndexChanged.connect(dialog._on_event_selection_changed)
    dialog.selected_event_enabled_checkbox.stateChanged.connect(dialog._on_selected_event_enabled_changed)
    dialog.compact_mode_button.clicked.connect(dialog._toggle_compact_mode)


def _build_full_page(dialog) -> QWidget:
    page = QWidget()
    layout = QVBoxLayout(page)

    dialog.tabs = QTabWidget()
    event_page = QWidget()
    event_layout = QVBoxLayout(event_page)

    events_group = QGroupBox("事件说明")
    events_layout = QVBoxLayout(events_group)
    dialog.event_description_label = QLabel("选择一个事件后可调整参数。")
    dialog.event_description_label.setWordWrap(True)
    dialog.event_summary_label = QLabel("")
    dialog.event_summary_label.setWordWrap(True)
    events_layout.addWidget(dialog.event_description_label)
    events_layout.addWidget(dialog.event_summary_label)
    event_layout.addWidget(events_group)

    params_group = QGroupBox("事件参数")
    params_group_layout = QVBoxLayout(params_group)
    dialog.params_scroll = QScrollArea()
    dialog.params_scroll.setWidgetResizable(True)
    dialog.params_container = QWidget()
    dialog.params_layout = QFormLayout(dialog.params_container)
    dialog.params_layout.addRow(QLabel("选择一个事件后可调整参数。"))
    dialog.params_scroll.setWidget(dialog.params_container)
    params_group_layout.addWidget(dialog.params_scroll)
    event_layout.addWidget(params_group, 1)

    status_page = QWidget()
    status_layout = QVBoxLayout(status_page)
    tasks_group = QGroupBox("事件触发状态")
    tasks_layout = QVBoxLayout(tasks_group)
    dialog.task_table = QTableWidget(0, 0)
    configure_task_table(dialog.task_table)
    tasks_layout.addWidget(dialog.task_table)
    status_layout.addWidget(tasks_group, 1)

    dialog.tabs.addTab(event_page, "事件参数")
    dialog.tabs.addTab(status_page, "触发状态")
    dialog.hook_panel = EventHookPanel()
    dialog.hook_panel.hooks_changed.connect(dialog._on_hooks_changed)
    dialog.tabs.addTab(dialog.hook_panel, "Hooks")
    layout.addWidget(dialog.tabs, 1)
    return page


def _build_compact_page(dialog) -> QWidget:
    page = QWidget()
    layout = QVBoxLayout(page)

    dialog.compact_event_description_label = QLabel("")
    dialog.compact_event_summary_label = QLabel("")
    dialog.compact_event_description_label.hide()
    dialog.compact_event_summary_label.hide()

    params_group = QGroupBox("常用参数")
    params_group_layout = QVBoxLayout(params_group)
    dialog.compact_params_scroll = QScrollArea()
    dialog.compact_params_scroll.setWidgetResizable(True)
    dialog.compact_params_scroll.setMinimumHeight(360)
    dialog.compact_params_container = QWidget()
    dialog.compact_params_container.setMinimumWidth(640)
    dialog.compact_params_layout = QFormLayout(dialog.compact_params_container)
    dialog.compact_params_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
    dialog.compact_params_layout.setRowWrapPolicy(QFormLayout.WrapLongRows)
    dialog.compact_params_layout.addRow(QLabel("选择一个事件后可调整参数。"))
    dialog.compact_params_scroll.setWidget(dialog.compact_params_container)
    params_group_layout.addWidget(dialog.compact_params_scroll)
    layout.addWidget(params_group, 5)

    tasks_group = QGroupBox("触发状态")
    tasks_layout = QVBoxLayout(tasks_group)
    dialog.compact_task_table = QTableWidget(0, 0)
    configure_task_table(dialog.compact_task_table, compact=True)
    dialog.compact_task_table.setMaximumHeight(180)
    tasks_layout.addWidget(dialog.compact_task_table)
    layout.addWidget(tasks_group, 1)
    return page


def _build_footer(dialog, layout: QVBoxLayout) -> None:
    footer = QHBoxLayout()
    dialog.status_label = QLabel("未加载地图")
    dialog.refresh_button = QPushButton("刷新")
    dialog.reset_portal_button = QPushButton("刷新事件状态")
    dialog.test_portal_button = QPushButton("测试传送门")
    dialog.test_portal_button.setCheckable(True)
    dialog.save_button = QPushButton("保存配置")
    dialog.refresh_button.clicked.connect(dialog.refresh)
    dialog.reset_portal_button.clicked.connect(dialog.reset_events_requested.emit)
    dialog.test_portal_button.clicked.connect(lambda _checked=False: dialog.test_portal_requested.emit())
    dialog.save_button.clicked.connect(dialog.save_requested.emit)
    footer.addWidget(dialog.status_label, 1)
    footer.addWidget(dialog.refresh_button)
    footer.addWidget(dialog.reset_portal_button)
    footer.addWidget(dialog.test_portal_button)
    footer.addWidget(dialog.save_button)
    layout.addLayout(footer)
