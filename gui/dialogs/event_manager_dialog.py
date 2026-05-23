from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QSignalBlocker
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from core.events.config import build_tui_event_options


class EventManagerDialog(QDialog):
    """Non-modal UI for complete event-package enablement and live task state."""

    config_changed = Signal(object)
    save_requested = Signal()
    test_portal_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("事件管理")
        self.setModal(False)
        self.resize(760, 520)

        self.registry = None
        self.config = None
        self.coordinator = None
        self.map_name = ""
        self._event_checkboxes: dict[str, QCheckBox] = {}

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        self.map_label = QLabel("地图: -")
        self.global_enabled_checkbox = QCheckBox("启用事件系统")
        self.global_enabled_checkbox.stateChanged.connect(self._on_global_enabled_changed)
        header.addWidget(self.map_label, 1)
        header.addWidget(self.global_enabled_checkbox)
        layout.addLayout(header)

        events_group = QGroupBox("事件选配")
        events_layout = QVBoxLayout(events_group)
        self.event_table = QTableWidget(0, 5)
        self.event_table.setHorizontalHeaderLabels(["启用", "完整事件", "优先级", "说明", "当前配置"])
        self.event_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.event_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.event_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        events_layout.addWidget(self.event_table)
        layout.addWidget(events_group, 1)

        tasks_group = QGroupBox("事件触发状态")
        tasks_layout = QVBoxLayout(tasks_group)
        self.task_table = QTableWidget(0, 8)
        self.task_table.setHorizontalHeaderLabels([
            "ID",
            "事件",
            "状态",
            "识别次数",
            "置信度",
            "地图坐标",
            "尝试次数",
            "最近识别",
        ])
        self.task_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.task_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.task_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        tasks_layout.addWidget(self.task_table)
        layout.addWidget(tasks_group, 2)

        footer = QHBoxLayout()
        self.status_label = QLabel("未加载地图")
        self.refresh_button = QPushButton("刷新")
        self.test_portal_button = QPushButton("测试传送门")
        self.test_portal_button.setCheckable(True)
        self.save_button = QPushButton("保存配置")
        self.refresh_button.clicked.connect(self.refresh)
        self.test_portal_button.clicked.connect(self.test_portal_requested.emit)
        self.save_button.clicked.connect(self.save_requested.emit)
        footer.addWidget(self.status_label, 1)
        footer.addWidget(self.refresh_button)
        footer.addWidget(self.test_portal_button)
        footer.addWidget(self.save_button)
        layout.addLayout(footer)

    def set_context(self, registry, config, coordinator=None, map_name: str = "") -> None:
        self.registry = registry
        self.config = config
        self.coordinator = coordinator
        self.map_name = map_name or ""
        self.refresh()

    def refresh(self) -> None:
        self._refresh_events()
        self._refresh_tasks()

    def _refresh_events(self) -> None:
        self._event_checkboxes.clear()
        self.event_table.setRowCount(0)
        self.map_label.setText(f"地图: {self.map_name or '-'}")

        if not self.registry or not self.config:
            self.global_enabled_checkbox.setEnabled(False)
            self.event_table.setRowCount(0)
            self.test_portal_button.setEnabled(False)
            self.status_label.setText("未加载事件配置")
            return

        self.global_enabled_checkbox.setEnabled(True)
        self.test_portal_button.setEnabled(True)
        with QSignalBlocker(self.global_enabled_checkbox):
            self.global_enabled_checkbox.setChecked(bool(getattr(self.config, "enabled", True)))

        options = build_tui_event_options(self.registry, self.config)
        self.event_table.setRowCount(len(options))
        for row, option in enumerate(options):
            event_type = str(option["event_type"])
            checkbox = QCheckBox()
            checkbox.setChecked(bool(option.get("enabled", True)))
            checkbox.stateChanged.connect(
                lambda _state, current_event=event_type: self._on_event_enabled_changed(current_event)
            )
            self._event_checkboxes[event_type] = checkbox
            self.event_table.setCellWidget(row, 0, checkbox)
            self._set_item(row, 1, str(option.get("display_name") or event_type))
            self._set_item(row, 2, str(option.get("current_values", {}).get("priority", "")))
            self._set_item(row, 3, str(option.get("description", "")))
            self._set_item(row, 4, self._format_current_values(option.get("current_values", {})))

        self.status_label.setText(f"{len(options)} 个完整事件，{len(self._current_tasks())} 个已识别任务")

    def _refresh_tasks(self) -> None:
        tasks = self._current_tasks()
        self.task_table.setRowCount(len(tasks))
        for row, task in enumerate(tasks):
            self._set_task_item(row, 0, task.id)
            self._set_task_item(row, 1, task.event_type)
            self._set_task_item(row, 2, self._state_text(task.state))
            self._set_task_item(row, 3, str(task.seen_count))
            self._set_task_item(row, 4, f"{float(task.confidence):.2f}")
            self._set_task_item(row, 5, f"({task.global_pos[0]}, {task.global_pos[1]})")
            self._set_task_item(row, 6, str(task.attempts))
            self._set_task_item(row, 7, str(task.last_seen_ms))
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
        checkbox = self._event_checkboxes.get(event_type)
        event_config["enabled"] = bool(checkbox.isChecked()) if checkbox else True
        self.config_changed.emit(self.config)
        self.refresh()

    def _set_item(self, row: int, column: int, text: str) -> None:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        self.event_table.setItem(row, column, item)

    def _set_task_item(self, row: int, column: int, text: str) -> None:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        self.task_table.setItem(row, column, item)

    def _state_text(self, state) -> str:
        value = getattr(state, "value", str(state))
        return {
            "observed": "已发现",
            "pending": "待处理",
            "running": "处理中",
            "completed": "已完成",
            "failed": "失败",
            "ignored": "已忽略",
        }.get(str(value).lower(), str(value))

    def _format_current_values(self, values: dict) -> str:
        keys = ["interaction", "minimap_threshold", "stable_frames", "arrival_radius", "interact_radius", "retry_limit"]
        parts = []
        for key in keys:
            if key in values:
                parts.append(f"{key}={values[key]}")
        return ", ".join(parts)
