
import json

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QGroupBox, QCheckBox,
    QSpinBox, QTextEdit, QApplication, QComboBox, QDoubleSpinBox,
    QInputDialog, QMessageBox
)
from PySide6.QtCore import Qt, QTimer, QPoint, QSignalBlocker

from ..selection.region_overlay import TransparentOverlay
from ..selection.center_selector import CenterPointSelector
from ..dialogs.color_picker_dialog import ColorPickerDialog
from ..widgets.scalable_map import ScalableMapWidget
from ..widgets.collapsible_group import CollapsibleMapGroup
from ..dialogs.advanced_settings_dialog import AdvancedSettingsDialog
from .mapping.save_load import (
    build_mapping_config,
    ensure_map_folder,
    load_root_config,
    save_map_config,
    save_root_config,
)
from .mapping.map_renderer import (
    pixmap_from_bgr,
    render_global_map_pixmap,
    unpack_enhanced_map_result,
)
from .mapping.params_adapter import (
    apply_hsv_toggles,
    apply_merge_weight,
    feature_params_from_widgets,
    sync_geometry_widgets,
    sync_recognizer_widgets,
    sync_stitcher_widgets,
)

class MappingWidget(QWidget):
    """绘图模式专属控件"""

    def __init__(self, app_context, main_window, parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.main_window = main_window

        # 状态变量
        self.overlay_active = False
        self.center_selector_active = False
        self.nav_path = None
        self.map_crop_offset = (0, 0)
        self.monitor_center = None # 物理中心点
        self.last_capture_size = None
        self.last_player_local_pos = None

        # 定时器
        self.capture_timer = QTimer()
        self.capture_timer.timeout.connect(self.capture_and_process)

        # UI 组件
        self.overlay = TransparentOverlay()
        self.overlay.hide()

        self.setup_ui()
        self.load_saved_params()

    def setup_ui(self):
        """设置界面"""
        layout = QHBoxLayout(self)
        control_panel = self.create_control_panel()
        layout.addWidget(control_panel, 1)
        display_panel = self.create_display_panel()
        layout.addWidget(display_panel, 3)

    def create_control_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Region Selection
        region_group = QGroupBox("1. 监控区域")
        region_layout = QVBoxLayout()
        self.select_region_btn = QPushButton("🖱️ 画框选择区域")
        self.select_region_btn.clicked.connect(self.select_region)
        region_layout.addWidget(self.select_region_btn)
        self.select_center_btn = QPushButton("🎯 选择人物中心点")
        self.select_center_btn.clicked.connect(self.select_center_point)
        region_layout.addWidget(self.select_center_btn)
        self.size_label = QLabel("截图大小:")
        region_layout.addWidget(self.size_label)
        self.size_spin = QSpinBox()
        self.size_spin.setRange(100, 1000)
        self.size_spin.setValue(320)
        self.size_spin.valueChanged.connect(self.update_capture_size)
        region_layout.addWidget(self.size_spin)
        self.color_picker_btn = QPushButton("🎨 选择颜色")
        self.color_picker_btn.clicked.connect(self.open_color_picker)
        self.color_picker_btn.setEnabled(False)
        region_layout.addWidget(self.color_picker_btn)
        self.region_label = QLabel("未选择区域")
        self.region_label.setWordWrap(True)
        region_layout.addWidget(self.region_label)
        region_group.setLayout(region_layout)
        layout.addWidget(region_group)

        # Monitoring Control
        monitor_group = QGroupBox("2. 监控控制")
        monitor_layout = QVBoxLayout()
        fps_layout = QHBoxLayout()
        fps_layout.addWidget(QLabel("帧率(FPS):"))
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 60)
        self.fps_spin.setValue(10)
        fps_layout.addWidget(self.fps_spin)
        monitor_layout.addLayout(fps_layout)
        self.start_btn = QPushButton("▶️ 开始监控")
        self.start_btn.clicked.connect(self.toggle_monitoring)
        self.start_btn.setEnabled(False)
        monitor_layout.addWidget(self.start_btn)
        self.reset_btn = QPushButton("🔄 重置地图")
        self.reset_btn.clicked.connect(self.reset_map)
        monitor_layout.addWidget(self.reset_btn)
        self.save_btn = QPushButton("💾 保存地图")
        self.save_btn.clicked.connect(self.save_map)
        monitor_layout.addWidget(self.save_btn)
        
        self.topmost_check = QCheckBox("置顶显示")
        self.topmost_check.setChecked(True)
        self.topmost_check.stateChanged.connect(self.update_topmost)
        monitor_layout.addWidget(self.topmost_check)
        
        monitor_group.setLayout(monitor_layout)
        layout.addWidget(monitor_group)

        geometry_group = QGroupBox("3. 高清绘图参数 (新地图生效)")
        geometry_layout = QVBoxLayout()

        self.draw_scale_spin = QDoubleSpinBox()
        self.draw_scale_spin.setRange(1.0, 4.0)
        self.draw_scale_spin.setSingleStep(0.5)
        self.draw_scale_spin.setDecimals(1)
        self.draw_scale_spin.setValue(float(self.app_context.stitcher.draw_scale))
        self.draw_scale_spin.valueChanged.connect(self.update_geometry_params)
        geometry_layout.addWidget(QLabel("绘图倍率 Draw Scale"))
        geometry_layout.addWidget(self.draw_scale_spin)

        self.canvas_size_spin = QSpinBox()
        self.canvas_size_spin.setRange(3000, 12000)
        self.canvas_size_spin.setSingleStep(500)
        self.canvas_size_spin.setValue(int(self.app_context.stitcher.canvas_size))
        self.canvas_size_spin.valueChanged.connect(self.update_geometry_params)
        geometry_layout.addWidget(QLabel("画布大小 Canvas Size"))
        geometry_layout.addWidget(self.canvas_size_spin)

        self.player_clear_radius_spin = QSpinBox()
        self.player_clear_radius_spin.setRange(0, 120)
        self.player_clear_radius_spin.setSingleStep(2)
        self.player_clear_radius_spin.setValue(int(getattr(self.app_context.recognizer, "player_clear_radius", 22)))
        self.player_clear_radius_spin.valueChanged.connect(self.update_geometry_params)
        geometry_layout.addWidget(QLabel("人物动态擦除半径(小地图像素)"))
        geometry_layout.addWidget(self.player_clear_radius_spin)

        self.wall_close_kernel_spin = QSpinBox()
        self.wall_close_kernel_spin.setRange(1, 15)
        self.wall_close_kernel_spin.setSingleStep(2)
        self.wall_close_kernel_spin.setValue(int(getattr(self.app_context.stitcher, "wall_close_kernel_size", 3)))
        self.wall_close_kernel_spin.valueChanged.connect(self.update_geometry_params)
        geometry_layout.addWidget(QLabel("墙体闭运算核(奇数)"))
        geometry_layout.addWidget(self.wall_close_kernel_spin)

        geometry_hint = QLabel("draw_scale/canvas_size 只在重置地图后生效；推荐 3.0 + 7500。")
        geometry_hint.setWordWrap(True)
        geometry_layout.addWidget(geometry_hint)

        geometry_group.setLayout(geometry_layout)
        layout.addWidget(geometry_group)

        # Merge Parameters
        merge_group = QGroupBox("3. 融合参数 (Weighted Merge)")
        merge_layout = QVBoxLayout()
        info_label = QLabel("当前采用高精度加权融合模式。\n该模式通过累积多帧置信度来消除噪音。")
        info_label.setWordWrap(True)
        merge_layout.addWidget(info_label)
        self.weight_label = QLabel("单帧置信度增量 (0.1-1.0):")
        merge_layout.addWidget(self.weight_label)
        self.weight_spin = QDoubleSpinBox()
        self.weight_spin.setRange(0.05, 1.0)
        self.weight_spin.setSingleStep(0.05)
        self.weight_spin.setValue(0.3)
        self.weight_spin.valueChanged.connect(self.update_merge_params)
        merge_layout.addWidget(self.weight_spin)
        merge_group.setLayout(merge_layout)
        layout.addWidget(merge_group)

        # HSV Parameters
        hsv_group = QGroupBox("4. HSV参数")
        hsv_layout = QVBoxLayout()
        self.wall_check = QCheckBox("墙壁识别")
        self.wall_check.setChecked(True)
        self.wall_check.stateChanged.connect(self.update_hsv_params)
        hsv_layout.addWidget(self.wall_check)
        self.fog_check = QCheckBox("迷雾识别")
        self.fog_check.setChecked(True)
        self.fog_check.stateChanged.connect(self.update_hsv_params)
        hsv_layout.addWidget(self.fog_check)
        hsv_group.setLayout(hsv_layout)
        layout.addWidget(hsv_group)

        # Feature Parameters
        feature_group = QGroupBox("5. 特征参数")
        feature_layout = QVBoxLayout()

        self.clahe_check = QCheckBox("启用CLAHE增强")
        self.clahe_check.setChecked(True)  # 默认开启
        self.clahe_check.stateChanged.connect(self.update_feature_params)
        feature_layout.addWidget(self.clahe_check)

        self.deepen_check = QCheckBox("启用颜色深化(蓝)")
        self.deepen_check.setChecked(True)  # 默认开启
        self.deepen_check.stateChanged.connect(self.update_feature_params)
        feature_layout.addWidget(self.deepen_check)

        # 权重调整
        self.wall_weight_spin = QSpinBox()
        self.wall_weight_spin.setRange(0, 100)
        self.wall_weight_spin.setValue(50)
        self.wall_weight_spin.valueChanged.connect(self.update_feature_params)
        feature_layout.addWidget(QLabel("墙壁权重"))
        feature_layout.addWidget(self.wall_weight_spin)

        self.edge_weight_spin = QSpinBox()
        self.edge_weight_spin.setRange(0, 100)
        self.edge_weight_spin.setValue(30)
        self.edge_weight_spin.valueChanged.connect(self.update_feature_params)
        feature_layout.addWidget(QLabel("边缘权重"))
        feature_layout.addWidget(self.edge_weight_spin)

        self.gray_weight_spin = QSpinBox()
        self.gray_weight_spin.setRange(0, 100)
        self.gray_weight_spin.setValue(20)
        self.gray_weight_spin.valueChanged.connect(self.update_feature_params)
        feature_layout.addWidget(QLabel("灰度权重"))
        feature_layout.addWidget(self.gray_weight_spin)

        # Canny阈值
        self.canny_low_spin = QSpinBox()
        self.canny_low_spin.setRange(0, 255)
        self.canny_low_spin.setValue(50)
        self.canny_low_spin.valueChanged.connect(self.update_feature_params)
        feature_layout.addWidget(QLabel("Canny低阈值"))
        feature_layout.addWidget(self.canny_low_spin)

        self.canny_high_spin = QSpinBox()
        self.canny_high_spin.setRange(0, 255)
        self.canny_high_spin.setValue(150)
        self.canny_high_spin.valueChanged.connect(self.update_feature_params)
        feature_layout.addWidget(QLabel("Canny高阈值"))
        feature_layout.addWidget(self.canny_high_spin)

        # 高级参数调节按钮
        self.advanced_settings_btn = QPushButton("⚙️ 高级参数调节")
        self.advanced_settings_btn.clicked.connect(self.open_advanced_settings)
        feature_layout.addWidget(self.advanced_settings_btn)
        feature_group.setLayout(feature_layout)
        layout.addWidget(feature_group)

        # Statistics
        stats_group = QGroupBox("6. 统计信息")
        stats_layout = QVBoxLayout()
        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        self.stats_text.setMaximumHeight(150)
        stats_layout.addWidget(self.stats_text)
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        layout.addStretch()
        return panel

    def create_display_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        capture_group = QGroupBox("当前视野 (实时)")
        capture_layout = QVBoxLayout()
        self.capture_label = QLabel()
        self.capture_label.setAlignment(Qt.AlignCenter)
        self.capture_label.setMinimumSize(200, 200)
        self.capture_label.setStyleSheet("background-color: black;")
        capture_layout.addWidget(self.capture_label)
        capture_group.setLayout(capture_layout)
        layout.addWidget(capture_group, 1)
        self.global_group = CollapsibleMapGroup("全局拼接地图 (点击设置导航点)")
        self.global_map_widget = self.global_group.scalable_map
        self.global_map_widget.setStyleSheet("background-color: black;")
        self.global_map_widget.pixel_clicked.connect(self.on_map_click)
        layout.addWidget(self.global_group, 3)
        return panel

    def _compute_scale(self):
        screen = QApplication.primaryScreen()
        return screen.devicePixelRatio(), screen.devicePixelRatio()

    def select_region(self):
        if self.overlay_active: return
        self.overlay_active = True
        self.overlay.region_selected.connect(self.on_region_selected)
        self.overlay.destroyed.connect(lambda: setattr(self, 'overlay_active', False))
        self.overlay.showFullScreen()

    def on_region_selected(self, x, y, width, height):
        sx, sy = self._compute_scale()
        px_left, px_top, px_w, px_h = int(x * sx), int(y * sy), int(width * sx), int(height * sy)
        self.app_context.monitor_region = {'left': px_left, 'top': px_top, 'width': px_w, 'height': px_h}
        self.app_context.monitor_logical_center = None
        self.region_label.setText(f"物理: ({px_left}, {px_top}) {px_w}x{px_h}")
        self.start_btn.setEnabled(True)
        self.color_picker_btn.setEnabled(True)
        self.save_config()

    def select_center_point(self):
        if self.center_selector_active: return
        self.center_selector_active = True
        self.center_selector = CenterPointSelector()
        self.center_selector.point_selected.connect(self.on_center_selected)
        self.center_selector.destroyed.connect(lambda: setattr(self, 'center_selector_active', False))
        self.center_selector.showFullScreen()

    def on_center_selected(self, x, y):
        self.app_context.monitor_logical_center = (x, y)
        self.app_context.monitor_size = self.size_spin.value()
        self.app_context.monitor_region = None
        sx, sy = self._compute_scale()
        self.monitor_center = (int(x * sx), int(y * sy)) # Keep physical center for capture
        self.region_label.setText(f"逻辑: ({x}, {y}), 物理: {self.monitor_center}, 大小: {self.app_context.monitor_size}")
        self.start_btn.setEnabled(True)
        self.color_picker_btn.setEnabled(True)
        self.save_config()

    def update_capture_size(self, size):
        self.app_context.monitor_size = size
        if self.app_context.monitor_logical_center:
            self.on_center_selected(*self.app_context.monitor_logical_center)

    def open_color_picker(self):
        if not self.app_context.monitor_region and not self.app_context.monitor_logical_center:
            return

        if self.app_context.monitor_logical_center:
            screenshot = self.app_context.screen_capture.capture_square(*self.monitor_center, self.app_context.monitor_size)
        else:
            region = self.app_context.monitor_region
            screenshot = self.app_context.screen_capture.capture(region['left'], region['top'], region['width'], region['height'])
        
        dialog = ColorPickerDialog(screenshot, self, recognizer_params=self.app_context.recognizer.get_params())
        if dialog.exec():
            result = dialog.get_result()
            if result['wall_hsv']:
                min_hsv, max_hsv = result['wall_hsv']
                self.app_context.recognizer.wall_hsv_min = min_hsv
                self.app_context.recognizer.wall_hsv_max = max_hsv
            if result['player_hsv']:
                min_hsv, max_hsv = result['player_hsv']
                self.app_context.recognizer.player_hsv_min = min_hsv
                self.app_context.recognizer.player_hsv_max = max_hsv
            self.save_config()

    def toggle_monitoring(self):
        self.app_context.monitoring = not self.app_context.monitoring
        if self.app_context.monitoring:
            if not self.app_context.monitor_region and not self.app_context.monitor_logical_center:
                self.app_context.monitoring = False
                QMessageBox.warning(self, "提示", "请先选择一个监控区域或中心点。")
                return
            self.capture_timer.start(1000 // self.fps_spin.value())
            self.start_btn.setText("⏸️ 停止监控")
        else:
            self.capture_timer.stop()
            self.start_btn.setText("▶️ 开始监控")

    def capture_and_process(self):
        if not self.app_context.monitoring: return

        if self.app_context.monitor_logical_center:
            img = self.app_context.screen_capture.capture_square(*self.monitor_center, self.app_context.monitor_size)
            player_pos = (self.app_context.monitor_size // 2, self.app_context.monitor_size // 2)
        else:
            region = self.app_context.monitor_region
            img = self.app_context.screen_capture.capture(region['left'], region['top'], region['width'], region['height'])
            player_mask = self.app_context.recognizer.extract_player(img)
            player_pos = self.app_context.tracker.detect_player(player_mask)
            if player_pos is None:
                if self.last_player_local_pos is not None:
                    player_pos = self.last_player_local_pos
                else:
                    h_img, w_img = img.shape[:2]
                    player_pos = (w_img // 2, h_img // 2)

        combined, wall_mask, fog_mask = self.app_context.recognizer.extract_combined(img, player_pos=player_pos)
        raw_gray = self.app_context.recognizer.get_raw_gray(img)
        self.app_context.stitcher.add_frame(img, combined, wall_mask, fog_mask, raw_gray=raw_gray, player_pos=player_pos)

        h_img, w_img = img.shape[:2]
        self.last_capture_size = (w_img, h_img)
        self.last_player_local_pos = player_pos

        self.update_displays(
            self.app_context.recognizer.get_preprocessed_image(img),
            combined,
            player_pos=player_pos,
            capture_size=(w_img, h_img)
        )
        self.update_statistics()

    def update_displays(self, current_img, combined_mask, player_pos=None, capture_size=None):
        if current_img is not None:
            self._show_image(self.capture_label, current_img)

        result = self.app_context.stitcher.get_enhanced_map(margin=500)
        global_map, crop_x1, crop_y1 = unpack_enhanced_map_result(result)
        if global_map.size > 0:
            self.map_crop_offset = (crop_x1, crop_y1)
            capture_size = capture_size or self.last_capture_size
            player_pos = player_pos or self.last_player_local_pos
            pixmap = render_global_map_pixmap(
                global_map=global_map,
                crop_x1=crop_x1,
                crop_y1=crop_y1,
                nav_path=self.nav_path,
                current_position=self.app_context.stitcher.get_current_position(),
                draw_scale=self.app_context.stitcher.draw_scale,
                player_pos=player_pos,
                capture_size=capture_size,
            )
            self.global_map_widget.set_image(pixmap)


    def on_map_click(self, x, y):
        crop_x1, crop_y1 = self.map_crop_offset
        start_pos = (self.app_context.stitcher.current_x, self.app_context.stitcher.current_y)
        end_pos = (x + crop_x1, y + crop_y1)
        self.nav_path = self.app_context.path_finder.find_path(
            self.app_context.stitcher.wall_layer,
            start_pos,
            end_pos,
            explored_map=self.app_context.stitcher.explored_map,
        )
        self.update_displays(None, None)


    def _show_image(self, label, img):
        if img is None: return
        label.setPixmap(pixmap_from_bgr(img))

    def update_statistics(self):
        stats = self.app_context.stitcher.get_statistics()
        self.stats_text.setText(f"总帧数: {stats['total_frames']}\n成功匹配: {stats['successful_matches']}")

    def update_hsv_params(self):
        apply_hsv_toggles(self.app_context.recognizer, self.wall_check, self.fog_check)

    def update_feature_params(self):
        params = feature_params_from_widgets(
            clahe_check=self.clahe_check,
            deepen_check=self.deepen_check,
            wall_weight_spin=self.wall_weight_spin,
            edge_weight_spin=self.edge_weight_spin,
            gray_weight_spin=self.gray_weight_spin,
            canny_low_spin=self.canny_low_spin,
            canny_high_spin=self.canny_high_spin,
        )
        self.app_context.recognizer.set_params(params)
        self.save_config()

    def update_merge_params(self):
        apply_merge_weight(self.app_context.stitcher, self.weight_spin)

    def update_geometry_params(self):
        if self._stitcher_is_empty():
            self.app_context.stitcher.reinitialize_canvas(
                canvas_size=self.canvas_size_spin.value(),
                draw_scale=self.draw_scale_spin.value(),
                wall_close_kernel_size=self.wall_close_kernel_spin.value(),
            )
        self.app_context.recognizer.set_params({
            "player_clear_radius": self.player_clear_radius_spin.value(),
        })
        self.app_context.stitcher.set_params({
            "wall_close_kernel_size": self.wall_close_kernel_spin.value(),
        })
        self.save_config()

    def open_advanced_settings(self):
        current_params = self.app_context.recognizer.get_params()
        stitcher_params = self.app_context.stitcher.get_params()
        current_params.update(stitcher_params)

        dialog = AdvancedSettingsDialog(self, current_params)
        if dialog.exec():
            new_params = dialog.get_params()
            self.app_context.recognizer.set_params(new_params)
            self.app_context.stitcher.set_params(new_params)
            self.save_config()

    def reset_map(self):
        self.app_context.stitcher.reinitialize_canvas(
            canvas_size=self.canvas_size_spin.value(),
            draw_scale=self.draw_scale_spin.value(),
            wall_close_kernel_size=self.wall_close_kernel_spin.value(),
        )
        self.app_context.recognizer.set_params({
            "player_clear_radius": self.player_clear_radius_spin.value(),
        })
        self.app_context.tracker.reset()
        self.global_map_widget.set_image(None)
        self.stats_text.clear()
        self.save_config()

    def save_map(self):
        map_name, ok = QInputDialog.getText(self, '保存地图', '请输入地图名称:')
        if not ok or not map_name: return

        map_folder = ensure_map_folder(__file__, map_name)
        
        self.app_context.stitcher.save_map_package(str(map_folder))
        
        config_data = self._build_mapping_config_with_ui_overrides(include_draw_scale=True)
        save_map_config(map_folder, config_data)
        
        QMessageBox.information(self, "成功", f"地图 '{map_name}' 已保存!")

    def save_config(self):
        config = self._build_mapping_config_with_ui_overrides()
        save_root_config(__file__, config)

    def load_saved_params(self):
        try:
            config = load_root_config(__file__)
            if config is None:
                return

            self.app_context.monitor_logical_center = config.get('monitor_logical_center')
            self.app_context.monitor_size = config.get('monitor_size', 320)
            self.app_context.monitor_region = config.get('monitor_region')
            
            if self.app_context.monitor_logical_center:
                sx, sy = self._compute_scale()
                self.monitor_center = (int(self.app_context.monitor_logical_center[0] * sx), int(self.app_context.monitor_logical_center[1] * sy))
                self.region_label.setText(f"逻辑: {self.app_context.monitor_logical_center}, 物理: {self.monitor_center}, 大小: {self.app_context.monitor_size}")
                self.start_btn.setEnabled(True)
                self.color_picker_btn.setEnabled(True)
            elif self.app_context.monitor_region:
                region = self.app_context.monitor_region
                self.region_label.setText(f"物理: ({region['left']}, {region['top']}) {region['width']}x{region['height']}")
                self.start_btn.setEnabled(True)
                self.color_picker_btn.setEnabled(True)

            self.size_spin.setValue(self.app_context.monitor_size)
            self.fps_spin.setValue(config.get('fps', 10))

            if 'recognizer_params' in config:
                self.app_context.recognizer.set_params(config['recognizer_params'])
                sync_recognizer_widgets(
                    config['recognizer_params'],
                    clahe_check=self.clahe_check,
                    deepen_check=self.deepen_check,
                    wall_weight_spin=self.wall_weight_spin,
                    edge_weight_spin=self.edge_weight_spin,
                    gray_weight_spin=self.gray_weight_spin,
                    canny_low_spin=self.canny_low_spin,
                    canny_high_spin=self.canny_high_spin,
                )


            if 'stitcher_params' in config:
                if self._stitcher_is_empty():
                    self.app_context.stitcher.reinitialize_canvas(
                        canvas_size=config['stitcher_params'].get("canvas_size", self.app_context.stitcher.canvas_size),
                        draw_scale=config['stitcher_params'].get("draw_scale", self.app_context.stitcher.draw_scale),
                        wall_close_kernel_size=config['stitcher_params'].get(
                            "wall_close_kernel_size",
                            getattr(self.app_context.stitcher, "wall_close_kernel_size", 3),
                        ),
                    )
                self.app_context.stitcher.set_params(config['stitcher_params'])
                sync_stitcher_widgets(config['stitcher_params'], weight_spin=self.weight_spin)

            blockers = [
                QSignalBlocker(self.draw_scale_spin),
                QSignalBlocker(self.canvas_size_spin),
                QSignalBlocker(self.player_clear_radius_spin),
                QSignalBlocker(self.wall_close_kernel_spin),
            ]
            try:
                sync_geometry_widgets(
                    config.get('recognizer_params', {}),
                    config.get('stitcher_params', {}),
                    draw_scale_spin=self.draw_scale_spin,
                    canvas_size_spin=self.canvas_size_spin,
                    player_clear_radius_spin=self.player_clear_radius_spin,
                    wall_close_kernel_spin=self.wall_close_kernel_spin,
                )
            finally:
                del blockers

        except (json.JSONDecodeError, KeyError) as e:
            print(f"配置文件 'config.json' 加载失败或格式错误: {e}")

    def _build_mapping_config_with_ui_overrides(self, *, include_draw_scale: bool = False) -> dict:
        config = build_mapping_config(
            self.app_context,
            self.fps_spin.value(),
            include_draw_scale=include_draw_scale,
        )
        stitcher_params = dict(config.get("stitcher_params", {}))
        stitcher_params["draw_scale"] = float(self.draw_scale_spin.value())
        stitcher_params["canvas_size"] = int(self.canvas_size_spin.value())
        stitcher_params["wall_close_kernel_size"] = int(self.wall_close_kernel_spin.value())
        config["stitcher_params"] = stitcher_params
        if include_draw_scale:
            config["draw_scale"] = float(self.draw_scale_spin.value())

        recognizer_params = dict(config.get("recognizer_params", {}))
        recognizer_params["player_clear_radius"] = int(self.player_clear_radius_spin.value())
        config["recognizer_params"] = recognizer_params
        return config

    def _stitcher_is_empty(self) -> bool:
        return int(self.app_context.stitcher.stats.get("total_frames", 0)) == 0

    def update_topmost(self):
        if self.topmost_check.isChecked():
            self.main_window.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        else:
            self.main_window.setWindowFlag(Qt.WindowStaysOnTopHint, False)
        self.main_window.show()
