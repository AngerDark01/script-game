from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QWidget,
    QFileDialog,
)

from auto_modules.core.perception.algorithms.base import AlgorithmDescriptor, ParameterSpec


class ParameterEditor(QWidget):
    """Build a data-driven editor from an algorithm descriptor."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._fields: dict[str, QWidget] = {}
        self._specs: tuple[ParameterSpec, ...] = ()
        self._layout = QFormLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

    def set_descriptor(self, descriptor: AlgorithmDescriptor | None, values: dict[str, Any] | None = None) -> None:
        self._clear()
        if descriptor is None:
            self._layout.addRow(QLabel("Select an available algorithm."))
            return

        self._specs = descriptor.parameters
        values = values or {}
        for spec in self._specs:
            editor = self._create_editor(spec, values.get(spec.name, spec.default))
            self._fields[spec.name] = editor
            label = QLabel(spec.label)
            if spec.description:
                label.setToolTip(spec.description)
                editor.setToolTip(spec.description)
            self._layout.addRow(label, editor)

    def values(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for spec in self._specs:
            editor = self._fields.get(spec.name)
            if editor is None:
                continue
            result[spec.name] = self._read_value(spec, editor)
        return result

    def _clear(self) -> None:
        self._fields.clear()
        self._specs = ()
        while self._layout.rowCount():
            self._layout.removeRow(0)

    @staticmethod
    def _create_editor(spec: ParameterSpec, value: Any) -> QWidget:
        if spec.kind == "bool":
            editor = QCheckBox()
            editor.setChecked(bool(value))
            return editor
        if spec.kind == "choice":
            editor = QComboBox()
            for choice in spec.choices:
                editor.addItem(str(choice), choice)
            index = editor.findData(value)
            editor.setCurrentIndex(index if index >= 0 else 0)
            return editor
        if spec.kind == "int":
            editor = QSpinBox()
            editor.setRange(
                int(spec.minimum if spec.minimum is not None else -2_147_483_648),
                int(spec.maximum if spec.maximum is not None else 2_147_483_647),
            )
            editor.setValue(int(value if value is not None else spec.default or 0))
            return editor
        if spec.kind == "float":
            editor = QDoubleSpinBox()
            editor.setRange(
                float(spec.minimum if spec.minimum is not None else -1_000_000.0),
                float(spec.maximum if spec.maximum is not None else 1_000_000.0),
            )
            editor.setDecimals(4)
            editor.setSingleStep(0.05)
            editor.setValue(float(value if value is not None else spec.default or 0.0))
            return editor
        if spec.kind == "path":
            row = QWidget()
            layout = QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            field = QLineEdit(str(value or ""))
            browse = QPushButton("Browse")
            browse.setMaximumWidth(86)
            browse.clicked.connect(lambda: _browse_path(field))
            layout.addWidget(field, 1)
            layout.addWidget(browse)
            row._value_field = field  # type: ignore[attr-defined]
            return row
        editor = QLineEdit(str(value if value is not None else ""))
        return editor

    @staticmethod
    def _read_value(spec: ParameterSpec, editor: QWidget) -> Any:
        if spec.kind == "bool":
            return bool(getattr(editor, "isChecked")())
        if spec.kind == "choice":
            return getattr(editor, "currentData")()
        if spec.kind == "int":
            return int(getattr(editor, "value")())
        if spec.kind == "float":
            return float(getattr(editor, "value")())
        if spec.kind == "path":
            field = getattr(editor, "_value_field", None)
            return field.text().strip() if field is not None else ""
        return str(getattr(editor, "text")()).strip()


def _browse_path(field: QLineEdit) -> None:
    path, _ = QFileDialog.getOpenFileName(field, "Select template", "", "Images (*.png *.jpg *.jpeg *.bmp);;All files (*)")
    if path:
        field.setText(path)
