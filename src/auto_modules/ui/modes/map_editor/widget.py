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
    QLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
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

        self.sidebar_scroll = QScrollArea()
        self.sidebar_scroll.setObjectName("map_editor_sidebar_scroll")
        self.sidebar_scroll.setFixedWidth(316)
        self.sidebar_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.sidebar_scroll.setWidgetResizable(True)
        self.sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.sidebar_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.sidebar_content = QFrame()
        self.sidebar_content.setProperty("role", "surface")
        self.sidebar_content.setMinimumWidth(292)
        self.sidebar_content.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self.sidebar_scroll.setWidget(self.sidebar_content)
        sidebar_layout = QVBoxLayout(self.sidebar_content)
        sidebar_layout.setContentsMargins(14, 14, 14, 14)
        sidebar_layout.setSpacing(8)
        sidebar_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)

        title = QLabel("地图墙体编辑")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        sidebar_layout.addWidget(title)
        subtitle = QLabel("手动修正定位和寻路使用的墙体，不改写原始绘制地图。")
        subtitle.setWordWrap(True)
        subtitle.setProperty("role", "muted")
        sidebar_layout.addWidget(subtitle)

        map_group = QGroupBox("选择地图")
        map_layout = QHBoxLayout(map_group)
        self.map_combo = QComboBox()
        self.map_combo.setObjectName("map_editor_map_combo")
        self.load_map_button = QPushButton("加载地图")
        self.load_map_button.setProperty("role", "primary")
        self.load_map_button.setFixedWidth(108)
        map_layout.addWidget(self.map_combo, 1)
        map_layout.addWidget(self.load_map_button)
        sidebar_layout.addWidget(map_group)

        version_group = QGroupBox("墙体版本")
        version_layout = QVBoxLayout(version_group)
        self.active_version_label = QLabel("当前导航版本：未加载")
        self.active_version_label.setProperty("role", "muted")
        self.version_combo = QComboBox()
        self.version_combo.setObjectName("map_editor_version_combo")
        version_actions = QHBoxLayout()
        self.checkout_version_button = QPushButton("作为编辑基线")
        self.checkout_version_button.setObjectName("map_editor_checkout_version")
        self.activate_version_button = QPushButton("设为导航版本")
        self.activate_version_button.setObjectName("map_editor_activate_version")
        version_actions.addWidget(self.checkout_version_button)
        version_actions.addWidget(self.activate_version_button)
        version_layout.addWidget(self.active_version_label)
        version_layout.addWidget(self.version_combo)
        version_layout.addLayout(version_actions)
        sidebar_layout.addWidget(version_group)

        tool_group = QGroupBox("墙体修正工具")
        tool_layout = QVBoxLayout(tool_group)
        tool_buttons = QHBoxLayout()
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
        tool_buttons.addWidget(self.add_wall_button)
        tool_buttons.addWidget(self.erase_wall_button)
        radius_row = QHBoxLayout()
        radius_row.addWidget(QLabel("画笔半径"))
        radius_row.addWidget(self.brush_radius_spin, 1)
        tool_layout.addLayout(tool_buttons)
        tool_layout.addLayout(radius_row)
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
        self.reload_button = QPushButton("放弃草稿")
        self.reload_button.setToolTip("放弃当前未确认的墙体草稿，恢复当前编辑基线。")
        self.clear_button = QPushButton("重新载入地图")
        self.clear_button.setToolTip("从当前导航版本重新载入地图；未确认草稿会被放弃。")
        history_layout.addLayout(history_row)
        history_actions = QHBoxLayout()
        history_actions.addWidget(self.reload_button)
        history_actions.addWidget(self.clear_button)
        history_layout.addLayout(history_actions)
        sidebar_layout.addWidget(history_group)

        self.save_button = QPushButton("确认并保存为新版本")
        self.save_button.setObjectName("map_editor_save")
        self.save_button.setProperty("role", "success")
        sidebar_layout.addWidget(self.save_button)

        legend = QGroupBox("预览说明")
        legend_layout = QVBoxLayout(legend)
        legend_layout.setSpacing(5)
        legend_layout.addWidget(self._legend_label("#F8FAFC", "白色：当前草稿中的墙体"))
        legend_layout.addWidget(self._legend_label("#91A4B8", "黑色：可通行空白区域"))
        legend_layout.addWidget(self._legend_label("#91A4B8", "擦除后立即显示黑色；确认后才创建版本"))
        sidebar_layout.addWidget(legend)

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

        sidebar_layout.addStretch()
        sidebar_layout.activate()
        self.sidebar_content.setMinimumHeight(sidebar_layout.sizeHint().height())
        root_layout.addWidget(self.sidebar_scroll)
        root_layout.addLayout(workspace, 1)
        self._set_editor_enabled(False)

    def _connect_signals(self) -> None:
        self.load_map_button.clicked.connect(self.load_selected_map)
        self.checkout_version_button.clicked.connect(self.checkout_selected_version)
        self.activate_version_button.clicked.connect(self.activate_checked_out_version)
        self.add_wall_button.toggled.connect(lambda checked: checked and self._update_canvas_tool())
        self.erase_wall_button.toggled.connect(lambda checked: checked and self._update_canvas_tool())
        self.brush_radius_spin.valueChanged.connect(lambda _value: self._update_canvas_tool())
        self.undo_button.clicked.connect(self.undo)
        self.redo_button.clicked.connect(self.redo)
        self.reload_button.clicked.connect(self.reload_current_map)
        self.clear_button.clicked.connect(self.reload_selected_map)
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
        self._show_status(
            f"地图已加载，编辑基线为 {self.controller.checked_out_label}。擦除会直接显示黑色；确认后才保存为新版本。"
        )
        return True

    def save_current_map(self) -> bool:
        if self.controller is None:
            return False
        try:
            version = self.controller.confirm_as_new_version()
        except (OSError, ValueError) as error:
            self._show_status(f"保存失败：{error}", error=True)
            return False
        self._show_controller_layers(fit=False)
        self._update_editor_actions()
        self.map_saved.emit(str(self.controller.map_folder))
        self._show_status(
            f"已确认并保存为 {version.id}，它已成为当前导航版本。已运行的导航需要重新加载地图后才会使用它。"
        )
        return True

    def reload_current_map(self) -> bool:
        if self.controller is None:
            return self.load_selected_map()
        if self.controller.is_dirty:
            choice = QMessageBox.question(
                self,
                "放弃草稿",
                "当前墙体草稿尚未确认保存为新版本，是否放弃？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if choice != QMessageBox.StandardButton.Yes:
                return False
        try:
            self.controller.discard_changes()
        except ValueError as error:
            self._show_status(f"恢复草稿失败：{error}", error=True)
            return False
        self._show_controller_layers(fit=False)
        self._show_status(f"已恢复 {self.controller.checked_out_label} 的已确认墙体版本。")
        return True

    def reload_selected_map(self) -> bool:
        if self.controller is not None and self.controller.is_dirty:
            choice = QMessageBox.question(
                self,
                "重新载入地图",
                "当前草稿尚未确认保存为新版本，是否放弃并重新载入？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if choice != QMessageBox.StandardButton.Yes:
                return False
        return self.load_selected_map()

    def checkout_selected_version(self) -> bool:
        if self.controller is None:
            return False
        version_id = self.version_combo.currentData()
        if version_id == self.controller.source_version_id:
            return True
        if self.controller.is_dirty:
            choice = QMessageBox.question(
                self,
                "切换编辑基线",
                "当前草稿尚未确认保存为新版本，是否放弃并切换？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if choice != QMessageBox.StandardButton.Yes:
                return False
        try:
            self.controller.checkout_version(version_id)
        except (OSError, ValueError) as error:
            self._show_status(f"切换版本失败：{error}", error=True)
            return False
        self._show_controller_layers(fit=False)
        self._show_status(f"已检出 {self.controller.checked_out_label} 作为新的编辑基线。")
        return True

    def activate_checked_out_version(self) -> bool:
        if self.controller is None:
            return False
        if self.controller.is_dirty:
            self._show_status("请先确认保存草稿，或放弃草稿后再切换导航版本。", error=True)
            return False
        try:
            version = self.controller.activate_checked_out_version()
        except (OSError, ValueError) as error:
            self._show_status(f"设置导航版本失败：{error}", error=True)
            return False
        self._show_controller_layers(fit=False)
        self._show_status(f"{version.id} 已设为导航版本；导航重新加载地图后生效。")
        return True

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
        self.canvas.set_wall_layer(self.controller.preview_wall_layer)
        if fit:
            self.canvas.fit_map()
        width, height = self.controller.map_shape[1], self.controller.map_shape[0]
        self.map_info_label.setText(f"{self.controller.map_folder.name} · {width} × {height}")
        self._refresh_version_list()
        self._update_canvas_tool()
        self._update_editor_actions()

    def _set_editor_enabled(self, enabled: bool) -> None:
        for control in (
            self.add_wall_button,
            self.erase_wall_button,
            self.brush_radius_spin,
            self.version_combo,
            self.checkout_version_button,
            self.activate_version_button,
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
        self.save_button.setEnabled(controller.is_dirty or controller.source_version_id is None)
        self.reload_button.setEnabled(True)
        self.clear_button.setEnabled(True)
        self.checkout_version_button.setEnabled(True)
        self.activate_version_button.setEnabled(
            controller.source_version_id is not None and not controller.is_dirty
        )

    def _refresh_version_list(self) -> None:
        assert self.controller is not None
        self.version_combo.blockSignals(True)
        self.version_combo.clear()
        self.version_combo.addItem("原始地图（编辑基线）", None)
        active_id = self.controller.active_version_id
        for version in self.controller.versions:
            label = f"{version.id}{' · 当前导航' if version.id == active_id else ''}"
            self.version_combo.addItem(label, version.id)
        selected_index = self.version_combo.findData(self.controller.source_version_id)
        self.version_combo.setCurrentIndex(selected_index if selected_index >= 0 else 0)
        self.version_combo.blockSignals(False)
        active_label = active_id or "原始地图（尚未创建版本）"
        self.active_version_label.setText(f"当前导航版本：{active_label}")

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
