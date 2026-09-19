"""Torchlight follow actor editor and generic sequence-editor exports."""

from copy import deepcopy

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from ...events.action_sequence_editor import ChainEditor, ParallelGroupEditor, spin


class ActorEditor(QDialog):
    """Edit one Torchlight follow actor's recognizer and controller mapping."""

    def __init__(self, actor, parent=None):
        super().__init__(parent)
        self.setWindowTitle("角色识别与独立控制")
        self.resize(520, 650)
        self.actor = deepcopy(actor)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)
        self.identity = QLineEdit(actor["actor_id"])
        form.addRow("角色标识", self.identity)
        self.slot = spin(actor["controller"], 1, 2)
        form.addRow("虚拟手柄", self.slot)
        self.lag = spin(actor["lag_distance"], 0, 1000, True)
        form.addRow("沿B的轨迹保持距离（地图像素）", self.lag)
        self.algorithm = QComboBox()
        self.algorithm.addItems(["color", "template"])
        self.algorithm.setCurrentText(actor["algorithm"])
        form.addRow("颜色 / ID模板", self.algorithm)
        parameters = actor["parameters"]
        self.colors = {}
        for key, label, default, upper in [
            ("hue_min", "色相下限", 40, 179),
            ("hue_max", "色相上限", 80, 179),
            ("saturation_min", "饱和度下限", 100, 255),
            ("saturation_max", "饱和度上限", 255, 255),
            ("value_min", "亮度下限", 100, 255),
            ("value_max", "亮度上限", 255, 255),
            ("min_area", "标记最小面积", 2, 10000),
            ("max_area", "标记最大面积", 100, 10000),
        ]:
            self.colors[key] = spin(parameters.get(key, default), 0, upper)
            form.addRow(label, self.colors[key])
        self.template = QLineEdit(parameters.get("template_path", ""))
        form.addRow("ID模板图片", self.template)
        browse = QPushButton("选择模板图片")
        browse.clicked.connect(self._browse)
        form.addRow(browse)
        self.basis = []
        for label, value in zip(
            ("地图X → 摇杆X", "地图Y → 摇杆X", "地图X → 摇杆Y", "地图Y → 摇杆Y"),
            actor["basis"],
        ):
            widget = spin(value, -10, 10, True)
            self.basis.append(widget)
            form.addRow(label, widget)
        hint = QLabel(
            "颜色取原始小地图；两个人物必须使用不同的颜色范围或ID模板。\n"
            "默认Y轴反向：地图向下为正，Xbox向上为正。"
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择ID模板",
            "",
            "Images (*.png *.jpg *.bmp)",
        )
        if path:
            self.template.setText(path)

    def value(self):
        algorithm = self.algorithm.currentText()
        parameters = (
            {key: widget.value() for key, widget in self.colors.items()}
            if algorithm == "color"
            else {"template_path": self.template.text(), "threshold": 0.85}
        )
        return {
            "actor_id": self.identity.text().strip(),
            "controller": self.slot.value(),
            "lag_distance": self.lag.value(),
            "algorithm": algorithm,
            "parameters": parameters,
            "basis": [widget.value() for widget in self.basis],
        }


__all__ = ["ActorEditor", "ChainEditor", "ParallelGroupEditor", "spin"]
