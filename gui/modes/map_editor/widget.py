"""Workbench page for non-destructive map wall corrections."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...composition.paths import map_data_dir_from_file
from .canvas import WallEditorCanvas
from .controller import MapEditorController


class MapEditorWidget(QWidget):
    """Edit one saved map's wall corrections while preserving its base package."""

    map_saved = Signal(str)

    def __init__(
        self,
        *,
        source_file: str | Path = __file__,
        parent: QWidget | None = None,
        map_root: str | Path | None = None,
    ) -> None:
        super().__init__(parent)
        self._map_root = Path(map_root) if map_root is not None else map_data_dir_from_file(source_file)
        self.controller: MapEditorController | None = None
        self._build_ui()
        self._connect_signals()
        self.refresh_map_list()

    def _build_ui(self) -> None:
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(12)

        sidebar = QFrame()
        sidebar.setProperty("role", "surface")
        sidebar.setFixedWidth(292)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(14, 14, 14, 14)
        sidebar_layout.setSpacing(10)

        title = QLabel("地图墙体编辑")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        sidebar_layout.addWidget(title)
        subtitle = QLabel("手动修正定位和寻路使用的墙体，不改写原始绘制地图。")
        subtitle.setWordWrap(True)
        subtitle.setProperty("role", "muted")
        sidebar_layout.addWidget(subtitle)

        map_group = QGroupBox("选择地图")
        map_layout = QVBoxLayout(map_group)
        self.map_combo = QComboBox()
        self.map_combo.setObjectName("map_editor_map_combo")
        self.load_map_button = QPushButton("加载地图")
        self.load_map_button.setProperty("role", "primary")
        map_layout.addWidget(self.map_combo)
        map_layout.addWidget(self.load_map_button)
        sidebar_layout.addWidget(map_group)

        tool_group = QGroupBox("墙体修正工具")
        tool_layout = QVBoxLayout(tool_group)
        self.add_wall_button = QPushButton("＋ 增加墙体")
        self.add_wall_button.setObjectName("map_editor_add_tool")
        self.add_wall_button.setCheckable(True)
        self.add_wall_button.setChecked(True)
        self.erase_wall_button = QPushButton("－ 擦除墙体")
        self.erase_wall_button.setObjectName("map_editor_erase_tool")
        self.erase_wall_button.setCheckable(True)
        self.tool_button_group = QButtonGroup(self)
        self.tool_button_group.setExclusive(True)
        self.tool_button_group.addButton(self.add_wall_button)
        self.tool_button_group.addButton(self.erase_wall_button)
        self.brush_radius_spin = QSpinBox()
        self.brush_radius_spin.setObjectName("map_editor_brush_radius")
        self.brush_radius_spin.setRange(1, 500)
        self.brush_radius_spin.setValue(12)
        self.brush_radius_spin.setSuffix(" px")
        tool_layout.addWidget(self.add_wall_button)
        tool_layout.addWidget(self.erase_wall_button)
        tool_layout.addWidget(QLabel("画笔半径"))
        tool_layout.addWidget(self.brush_radius_spin)
        sidebar_layout.addWidget(tool_group)

        history_group = QGroupBox("编辑操作")
        history_layout = QVBoxLayout(history_group)
        history_row = QHBoxLayout()
        self.undo_button = QPushButton("撤销")
        self.undo_button.setObjectName("map_editor_undo")
        self.redo_button = QPushButton("重做")
        self.redo_button.setObjectName("map_editor_redo")
        history_row.addWidget(self.undo_button)
        history_row.addWidget(self.redo_button)
        self.reload_button = QPushButton("放弃未保存修改并重新加载")
        self.clear_button = QPushButton("清空人工修正")
        self.clear_button.setProperty("role", "warning")
        history_layout.addLayout(history_row)
        history_layout.addWidget(self.reload_button)
        history_layout.addWidget(self.clear_button)
        sidebar_layout.addWidget(history_group)

        self.save_button = QPushButton("保存墙体修正")
        self.save_button.setObjectName("map_editor_save")
        self.save_button.setProperty("role", "success")
        sidebar_layout.addWidget(self.save_button)

        legend = QGroupBox("图层说明")
        legend_layout = QVBoxLayout(legend)
        legend_layout.setSpacing(5)
        legend_layout.addWidget(self._legend_label("#A5B4C4", "灰白：原始墙体"))
        legend_layout.addWidget(self._legend_label("#EF4444", "红色：手动增加的墙体"))
        legend_layout.addWidget(self._legend_label("#22D3EE", "青色：手动擦除的原始墙体"))
        sidebar_layout.addWidget(legend)
        sidebar_layout.addStretch()

        workspace = QVBoxLayout()
        workspace.setSpacing(8)
        top_row = QHBoxLayout()
        self.map_info_label = QLabel("尚未加载地图")
        self.map_info_label.setProperty("role", "muted")
        self.zoom_out_button = QPushButton("－")
        self.zoom_out_button.setFixedWidth(42)
        self.fit_map_button = QPushButton("适应地图")
        self.zoom_in_button = QPushButton("＋")
        self.zoom_in_button.setFixedWidth(42)
        self.zoom_label = QLabel("100%")
        self.zoom_label.setMinimumWidth(52)
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_row.addWidget(self.map_info_label)
        top_row.addStretch()
        top_row.addWidget(self.zoom_out_button)
        top_row.addWidget(self.fit_map_button)
        top_row.addWidget(self.zoom_in_button)
        top_row.addWidget(self.zoom_label)
        workspace.addLayout(top_row)

        self.canvas = WallEditorCanvas(self)
        self.canvas.setObjectName("map_editor_canvas")
        workspace.addWidget(self.canvas, 1)

        status_frame = QFrame()
        status_frame.setProperty("role", "status")
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(9, 5, 9, 5)
        self.status_label = QLabel("选择一张已保存的地图，然后点击“加载地图”。")
        self.status_label.setObjectName("map_editor_status")
        self.status_label.setProperty("role", "status-value")
        self.status_label.setWordWrap(True)
        status_layout.addWidget(self.status_label)
        workspace.addWidget(status_frame)

        root_layout.addWidget(sidebar)
        root_layout.addLayout(workspace, 1)
        self._set_editor_enabled(False)

    def _connect_signals(self) -> None:
        self.load_map_button.clicked.connect(self.load_selected_map)
        self.add_wall_button.toggled.connect(lambda checked: checked and self._update_canvas_tool())
        self.erase_wall_button.toggled.connect(lambda checked: checked and self._update_canvas_tool())
        self.brush_radius_spin.valueChanged.connect(lambda _value: self._update_canvas_tool())
        self.undo_button.clicked.connect(self.undo)
        self.redo_button.clicked.connect(self.redo)
        self.reload_button.clicked.connect(self.reload_current_map)
        self.clear_button.clicked.connect(self.clear_overrides)
        self.save_button.clicked.connect(self.save_current_map)
        self.zoom_out_button.clicked.connect(lambda: self.canvas.set_zoom(self.canvas.zoom / 1.25))
        self.zoom_in_button.clicked.connect(lambda: self.canvas.set_zoom(self.canvas.zoom * 1.25))
        self.fit_map_button.clicked.connect(self.canvas.fit_map)
        self.canvas.zoom_changed.connect(self._update_zoom_label)
        self.canvas.stroke_started.connect(self._start_stroke)
        self.canvas.stroke_extended.connect(self._extend_stroke)
        self.canvas.stroke_finished.connect(self._finish_stroke)

    def refresh_map_list(self) -> None:
        """Refresh only folders that contain a valid saved map package."""
        previous_name = self.map_combo.currentText()
        maps = []
        if self._map_root.exists():
            maps = sorted(
                folder for folder in self._map_root.iterdir()
                if folder.is_dir() and (folder / "map_data.npz").is_file()
            )
        self.map_combo.blockSignals(True)
        self.map_combo.clear()
        if not maps:
            self.map_combo.addItem("未找到可编辑地图", None)
            self.load_map_button.setEnabled(False)
        else:
            for folder in maps:
                self.map_combo.addItem(folder.name, str(folder))
            selected = self.map_combo.findText(previous_name)
            self.map_combo.setCurrentIndex(selected if selected >= 0 else 0)
            self.load_map_button.setEnabled(True)
        self.map_combo.blockSignals(False)

    def load_selected_map(self) -> bool:
        folder_value = self.map_combo.currentData()
        if not folder_value:
            self._show_status("没有找到可加载的地图。", error=True)
            return False
        try:
            self.controller = MapEditorController.load(Path(folder_value))
        except (OSError, ValueError) as error:
            self.controller = None
            self.canvas.clear_map_layers()
            self._set_editor_enabled(False)
            self._show_status(f"地图加载失败：{error}", error=True)
            return False
        self._show_controller_layers(fit=True)
        self._set_editor_enabled(True)
        self._show_status("地图已加载。左键绘制，中键拖动画布，滚轮缩放。")
        return True

    def save_current_map(self) -> bool:
        if self.controller is None:
            return False
        try:
            path = self.controller.save()
        except (OSError, ValueError) as error:
            self._show_status(f"保存失败：{error}", error=True)
            return False
        self._update_editor_actions()
        self.map_saved.emit(str(self.controller.map_folder))
        self._show_status(
            f"已保存到 {path.name}。已运行的导航需要重新加载此地图后，定位和寻路才会使用新墙体。"
        )
        return True

    def reload_current_map(self) -> bool:
        if self.controller is None:
            return self.load_selected_map()
        if self.controller.is_dirty:
            choice = QMessageBox.question(
                self,
                "放弃未保存修改",
                "未保存的墙体修正将被放弃，是否继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if choice != QMessageBox.StandardButton.Yes:
                return False
        try:
            self.controller.discard_changes()
        except (OSError, ValueError) as error:
            self._show_status(f"重新加载失败：{error}", error=True)
            return False
        self._show_controller_layers(fit=False)
        self._show_status("已重新加载已保存的墙体修正。")
        return True

    def clear_overrides(self) -> None:
        if self.controller is None:
            return
        self.controller.clear_overrides()
        self._show_controller_layers(fit=False)
        self._show_status("人工墙体修正已清空；点击“保存墙体修正”后才写入文件。")

    def undo(self) -> None:
        if self.controller is not None and self.controller.undo():
            self.canvas.refresh_layers()
            self._update_editor_actions()
            self._show_status("已撤销上一次墙体绘制。")

    def redo(self) -> None:
        if self.controller is not None and self.controller.redo():
            self.canvas.refresh_layers()
            self._update_editor_actions()
            self._show_status("已重做上一次墙体绘制。")

    def _start_stroke(self, point: tuple[int, int]) -> None:
        if self.controller is None:
            return
        self.controller.begin_stroke()
        self._apply_stroke_point(point)

    def _extend_stroke(self, point: tuple[int, int]) -> None:
        self._apply_stroke_point(point)

    def _finish_stroke(self) -> None:
        if self.controller is None:
            return
        if self.controller.end_stroke():
            self._update_editor_actions()
            self._show_status("墙体修正已更新，尚未保存。")

    def _apply_stroke_point(self, point: tuple[int, int]) -> None:
        if self.controller is None:
            return
        mode = "add" if self.add_wall_button.isChecked() else "erase"
        changed = self.controller.apply_brush(
            point,
            radius=self.brush_radius_spin.value(),
            mode=mode,
        )
        if changed:
            self.canvas.refresh_layers()

    def _show_controller_layers(self, *, fit: bool) -> None:
        assert self.controller is not None
        self.canvas.set_map_layers(
            self.controller.base_wall_layer,
            self.controller.document.add_mask,
            self.controller.document.erase_mask,
        )
        if fit:
            self.canvas.fit_map()
        width, height = self.controller.map_shape[1], self.controller.map_shape[0]
        self.map_info_label.setText(f"{self.controller.map_folder.name} · {width} × {height}")
        self._update_canvas_tool()
        self._update_editor_actions()

    def _set_editor_enabled(self, enabled: bool) -> None:
        for control in (
            self.add_wall_button,
            self.erase_wall_button,
            self.brush_radius_spin,
            self.undo_button,
            self.redo_button,
            self.reload_button,
            self.clear_button,
            self.save_button,
            self.zoom_out_button,
            self.fit_map_button,
            self.zoom_in_button,
        ):
            control.setEnabled(enabled)
        self.canvas.setEnabled(enabled)

    def _update_editor_actions(self) -> None:
        controller = self.controller
        if controller is None:
            return
        self.undo_button.setEnabled(controller.can_undo)
        self.redo_button.setEnabled(controller.can_redo)
        self.save_button.setEnabled(controller.is_dirty)
        self.reload_button.setEnabled(True)
        self.clear_button.setEnabled(True)

    def _update_canvas_tool(self) -> None:
        self.canvas.set_tool(
            "add" if self.add_wall_button.isChecked() else "erase",
            self.brush_radius_spin.value(),
        )

    def _update_zoom_label(self, zoom: float) -> None:
        self.zoom_label.setText(f"{zoom * 100:.0f}%")

    @staticmethod
    def _legend_label(color: str, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(f"color: {color};")
        return label

    def _show_status(self, message: str, *, error: bool = False) -> None:
        self.status_label.setText(message)
        self.status_label.setStyleSheet("color: #FCA5A5;" if error else "")

