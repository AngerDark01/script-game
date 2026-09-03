from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.events.hooks import (
    EVENT_HOOK_COMPLETED,
    EVENT_HOOK_LABELS,
    EVENT_HOOK_VISIBLE_TARGET,
)
from core.events.hooks.instances import DEFAULT_KEY_PRESS_HOOK_KEY, KEY_PRESS_HOOK_TYPE


class EventHookPanel(QWidget):
    """Edit event hook action instances stored on EventSystemConfig."""

    hooks_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.config = None
        self.event_options: list[tuple[str, str]] = []
        self._syncing = False
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        self.description_label = QLabel("Hook 实例必须绑定事件类型，并可同时挂到多个触发时机。")
        layout.addWidget(self.description_label)

        self.table = QTableWidget(0, 0)
        self._configure_headers()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.table, 1)

        controls = QHBoxLayout()
        self.status_label = QLabel("未加载事件配置")
        self.add_key_hook_button = QPushButton("新增按键 Hook")
        self.remove_hook_button = QPushButton("删除选中")
        self.add_key_hook_button.clicked.connect(self.add_key_press_hook)
        self.remove_hook_button.clicked.connect(self.remove_selected_hook)
        controls.addWidget(self.status_label, 1)
        controls.addWidget(self.add_key_hook_button)
        controls.addWidget(self.remove_hook_button)
        layout.addLayout(controls)

    def set_config(self, config, event_options: list[dict] | None = None) -> None:
        self.config = config
        self.event_options = _event_options(event_options or [])
        self.refresh()

    def refresh(self) -> None:
        instances = self._instances()
        self._syncing = True
        try:
            self._configure_headers()
            self.table.setRowCount(len(instances))
            for row, instance in enumerate(instances):
                self._render_row(row, instance)
        finally:
            self._syncing = False
        has_config = self.config is not None
        self.add_key_hook_button.setEnabled(has_config)
        self.remove_hook_button.setEnabled(has_config and bool(instances))
        self.status_label.setText(
            f"{len(instances)} 个 Hook 实例" if has_config else "未加载事件配置"
        )

    def add_key_press_hook(self) -> None:
        if self.config is None:
            return
        instances = self._instances(create=True)
        instances.append(
            {
                "id": self._next_instance_id(instances),
                "type": KEY_PRESS_HOOK_TYPE,
                "name": "按键 Hook",
                "enabled": True,
                "key": DEFAULT_KEY_PRESS_HOOK_KEY,
                "event_types": _default_event_types(self.event_options),
                "triggers": [EVENT_HOOK_VISIBLE_TARGET],
            }
        )
        self.refresh()
        self.hooks_changed.emit()

    def remove_selected_hook(self) -> None:
        row = self.table.currentRow()
        instances = self._instances()
        if row < 0 or row >= len(instances):
            return
        instances.pop(row)
        self.refresh()
        self.hooks_changed.emit()

    def _render_row(self, row: int, instance: dict) -> None:
        enabled = QCheckBox()
        enabled.setChecked(bool(instance.get("enabled", True)))
        enabled.stateChanged.connect(
            lambda _state, current=instance, widget=enabled: self._set_enabled(current, widget.isChecked())
        )
        self.table.setCellWidget(row, 0, enabled)

        name_edit = QLineEdit(str(instance.get("name") or "按键 Hook"))
        name_edit.editingFinished.connect(
            lambda current=instance, widget=name_edit: self._set_text(current, "name", widget.text())
        )
        self.table.setCellWidget(row, 1, name_edit)

        self._set_item(row, 2, "按键")

        key_edit = QLineEdit(str(instance.get("key") or DEFAULT_KEY_PRESS_HOOK_KEY))
        key_edit.setMaxLength(32)
        key_edit.editingFinished.connect(
            lambda current=instance, widget=key_edit: self._set_text(current, "key", widget.text().strip().lower())
        )
        self.table.setCellWidget(row, 3, key_edit)

        column = 4
        for event_type, _label in self.event_options:
            self._set_event_type_checkbox(row, column, instance, event_type)
            column += 1
        self._set_trigger_checkbox(row, column, instance, EVENT_HOOK_VISIBLE_TARGET)
        self._set_trigger_checkbox(row, column + 1, instance, EVENT_HOOK_COMPLETED)

    def _configure_headers(self) -> None:
        labels = ["启用", "名称", "类型", "按键"]
        labels.extend(label for _event_type, label in self.event_options)
        labels.extend([
            EVENT_HOOK_LABELS[EVENT_HOOK_VISIBLE_TARGET],
            EVENT_HOOK_LABELS[EVENT_HOOK_COMPLETED],
        ])
        self.table.setColumnCount(len(labels))
        self.table.setHorizontalHeaderLabels(labels)

    def _set_event_type_checkbox(self, row: int, column: int, instance: dict, event_type: str) -> None:
        checkbox = QCheckBox()
        checkbox.setChecked(event_type in _event_type_list(instance))
        checkbox.stateChanged.connect(
            lambda _state, current=instance, current_event=event_type, widget=checkbox: self._set_event_type(
                current,
                current_event,
                widget.isChecked(),
            )
        )
        self.table.setCellWidget(row, column, checkbox)

    def _set_trigger_checkbox(self, row: int, column: int, instance: dict, hook_name: str) -> None:
        checkbox = QCheckBox()
        checkbox.setChecked(hook_name in _trigger_list(instance))
        checkbox.stateChanged.connect(
            lambda _state, current=instance, hook=hook_name, widget=checkbox: self._set_trigger(
                current,
                hook,
                widget.isChecked(),
            )
        )
        self.table.setCellWidget(row, column, checkbox)

    def _set_enabled(self, instance: dict, enabled: bool) -> None:
        if self._syncing:
            return
        instance["enabled"] = bool(enabled)
        self.hooks_changed.emit()

    def _set_text(self, instance: dict, key: str, value: str) -> None:
        if self._syncing:
            return
        instance[key] = str(value or "").strip()
        self.hooks_changed.emit()

    def _set_trigger(self, instance: dict, hook_name: str, enabled: bool) -> None:
        if self._syncing:
            return
        triggers = _trigger_list(instance)
        if enabled and hook_name not in triggers:
            triggers.append(hook_name)
        if not enabled:
            triggers = [item for item in triggers if item != hook_name]
        instance["triggers"] = triggers
        self.hooks_changed.emit()

    def _set_event_type(self, instance: dict, event_type: str, enabled: bool) -> None:
        if self._syncing:
            return
        event_types = _event_type_list(instance)
        if enabled and event_type not in event_types:
            event_types.append(event_type)
        if not enabled:
            event_types = [item for item in event_types if item != event_type]
        instance["event_types"] = event_types
        self.hooks_changed.emit()

    def _set_item(self, row: int, column: int, text: str) -> None:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, column, item)

    def _instances(self, *, create: bool = False) -> list[dict]:
        if self.config is None:
            return []
        hooks = getattr(self.config, "hooks", None)
        if not isinstance(hooks, dict):
            if not create:
                return []
            hooks = {}
            self.config.hooks = hooks
        instances = hooks.get("instances")
        if not isinstance(instances, list):
            if not create:
                return []
            instances = []
            hooks["instances"] = instances
        return instances

    def _next_instance_id(self, instances: list[dict]) -> str:
        existing = {str(item.get("id") or "") for item in instances}
        index = len(existing) + 1
        while f"key_press_{index}" in existing:
            index += 1
        return f"key_press_{index}"


def _trigger_list(instance: dict) -> list[str]:
    triggers = instance.get("triggers", [])
    if isinstance(triggers, str):
        return [triggers]
    if not isinstance(triggers, list):
        return []
    return [str(item) for item in triggers]


def _event_type_list(instance: dict) -> list[str]:
    event_types = instance.get("event_types")
    if event_types is None:
        event_types = instance.get("event_type", [])
    if isinstance(event_types, str):
        return [event_types]
    if not isinstance(event_types, list):
        return []
    return [str(item) for item in event_types]


def _event_options(options: list[dict]) -> list[tuple[str, str]]:
    result = []
    for option in options:
        event_type = str(option.get("event_type") or "").strip()
        if not event_type:
            continue
        label = str(option.get("display_name") or event_type)
        result.append((event_type, label))
    return result


def _default_event_types(options: list[tuple[str, str]]) -> list[str]:
    if not options:
        return []
    return [options[0][0]]
