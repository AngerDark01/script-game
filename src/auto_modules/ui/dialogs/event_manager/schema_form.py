from __future__ import annotations

from collections.abc import Callable, Iterable

from PySide6.QtCore import QSignalBlocker
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
)


def editable_schema_items(schema: dict, only_keys: Iterable[str] | None = None) -> list[tuple[str, dict]]:
    """Return editable schema fields in schema order, optionally filtered by key."""
    allowed = set(only_keys) if only_keys is not None else None
    return [
        (key, spec)
        for key, spec in schema.items()
        if key != "enabled"
        and bool(spec.get("editable", True))
        and (allowed is None or key in allowed)
    ]


def clear_param_form(layout: QFormLayout, widgets: dict[str, object], message: str = "") -> None:
    """Remove rendered parameter rows and optionally show an empty-state message."""
    while layout.rowCount():
        layout.removeRow(0)
    widgets.clear()
    if message:
        layout.addRow(QLabel(message))


def create_param_label(key: str, spec: dict) -> QLabel:
    label = QLabel(str(spec.get("label") or key))
    label.setWordWrap(True)
    tooltip = str(spec.get("help") or "")
    if tooltip:
        label.setToolTip(tooltip)
    return label


def create_param_widget(
    key: str,
    spec: dict,
    value,
    on_changed: Callable[[str, object], None],
):
    """Create a Qt editor for one event config schema field."""
    param_type = str(spec.get("type", "str"))
    default = spec.get("default", 0)
    if param_type == "float":
        widget = QDoubleSpinBox()
        widget.setDecimals(int(spec.get("decimals", 2)))
        widget.setRange(float(spec.get("min", -999999.0)), float(spec.get("max", 999999.0)))
        widget.setSingleStep(float(spec.get("step", 0.01)))
        set_widget_value(widget, value if value is not None else default, spec)
        widget.valueChanged.connect(lambda new_value, current_key=key: on_changed(current_key, float(new_value)))
        return widget
    if param_type == "int":
        widget = QSpinBox()
        widget.setRange(int(spec.get("min", -999999)), int(spec.get("max", 999999)))
        widget.setSingleStep(int(spec.get("step", 1)))
        set_widget_value(widget, value if value is not None else default, spec)
        widget.valueChanged.connect(lambda new_value, current_key=key: on_changed(current_key, int(new_value)))
        return widget
    if param_type == "bool":
        widget = QCheckBox()
        set_widget_value(widget, value if value is not None else default, spec)
        widget.stateChanged.connect(
            lambda _state, current_key=key, current_widget=widget: on_changed(
                current_key,
                bool(current_widget.isChecked()),
            )
        )
        return widget
    if param_type == "choice":
        widget = QComboBox()
        choices = [str(item) for item in spec.get("choices", [])]
        widget.addItems(choices)
        set_widget_value(widget, value if value is not None else (choices[0] if choices else ""), spec)
        widget.currentTextChanged.connect(lambda new_value, current_key=key: on_changed(current_key, str(new_value)))
        return widget
    if param_type == "str":
        widget = QLineEdit()
        set_widget_value(widget, value if value is not None else default, spec)
        widget.editingFinished.connect(
            lambda current_key=key, current_widget=widget: on_changed(current_key, current_widget.text())
        )
        return widget
    return QLabel(str(value if value is not None else default))


def set_widget_value(widget, value, spec: dict) -> None:
    """Write a schema value back to a supported Qt editor without emitting changes."""
    with QSignalBlocker(widget):
        if isinstance(widget, QDoubleSpinBox):
            widget.setValue(float(value if value is not None else spec.get("default", 0.0)))
            return
        if isinstance(widget, QSpinBox):
            widget.setValue(int(value if value is not None else spec.get("default", 0)))
            return
        if isinstance(widget, QCheckBox):
            widget.setChecked(bool(value if value is not None else spec.get("default", False)))
            return
        if isinstance(widget, QComboBox):
            choices = [str(item) for item in spec.get("choices", [])]
            current = str(value if value is not None else (choices[0] if choices else ""))
            index = widget.findText(current)
            if index >= 0:
                widget.setCurrentIndex(index)
            return
        if isinstance(widget, QLineEdit):
            widget.setText(str(value if value is not None else spec.get("default", "")))


def sync_param_widget_maps(
    widget_maps: Iterable[dict[str, object]],
    key: str,
    value,
    spec: dict | None,
) -> None:
    """Synchronize duplicate full/compact editors for one changed field."""
    if not spec:
        return
    for widgets in widget_maps:
        widget = widgets.get(key)
        if widget is not None:
            set_widget_value(widget, value, spec)
