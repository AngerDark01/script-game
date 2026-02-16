"""
修改后的主窗口，移除了当前捕获UI窗口，但保留了所有功能
"""

import sys
import os
import json
import ctypes
from datetime import datetime

import cv2
import numpy as np
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QGroupBox, QCheckBox,
    QSpinBox, QTextEdit, QApplication, QComboBox, QDoubleSpinBox,
    QStackedWidget, QInputDialog, QMessageBox
)
from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtGui import QImage, QPixmap

from core import ScreenCapture, HSVRecognizer, MapStitcher, PlayerTracker
from core.pathfinder import PathFinder
from .overlay import TransparentOverlay
from .center_selector import CenterPointSelector
from .color_picker import ColorPickerDialog
# 使用修复后的组件
from .widgets_fixed import ScalableMapWidget, CollapsibleMapGroup  # 使用修复后的组件
from .advanced_settings import AdvancedSettingsDialog
from .navigation_mode import NavigationModeWidget



class ImprovedMainWindow(QMainWindow):
    """改进的实时小地图监控主窗口 - 移除了当前捕获UI窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("实时小地图拼接系统（改进版）")
        self.setGeometry(100, 100, 1400, 900)

        # 设置窗口始终保持在最顶层
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        # 核心组件
        self.screen_capture = ScreenCapture()
        self.recognizer = HSVRecognizer()
        # 将画布调整为 5000x5000，足够大且性能更好
        self.stitcher = MapStitcher(canvas_size=5000)
        self.tracker = PlayerTracker()
        self.path_finder = PathFinder()
        self.nav_path = None
        self.map_crop_offset = (0, 0)

        # 监控状态
        self.monitor_region = None
        self.monitor_center = None  # 新增：中心点坐标
        self.monitor_size = 200     # 新增：截图大小，默认200x200
        self.monitoring = False
        self.overlay_active = False
        self.center_selector_active = False  # 新增：中心选择器状态

        # 定时器
        self.capture_timer = QTimer()
        self.capture_timer.timeout.connect(self.capture_and_process)

        # 界面
        self.overlay = TransparentOverlay() # 必须在 setup_ui 之前创建，导航模式需要
        self.overlay.hide() # 默认隐藏
        self.setup_ui()

        # 加载保存的参数
        self.load_saved_params()

    def setup_ui(self):
        """设置界面"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主垂直布局
        main_layout = QVBoxLayout(central_widget)
        
        # 1. 顶部模式切换栏
        mode_layout = QHBoxLayout()
        self.mode_btn_mapping = QPushButton("🗺️ 绘图模式")
        self.mode_btn_mapping.setCheckable(True)
        self.mode_btn_mapping.setChecked(True)
        self.mode_btn_mapping.clicked.connect(lambda: self.switch_mode(0))
        
        self.mode_btn_nav = QPushButton("🧭 导航模式")
        self.mode_btn_nav.setCheckable(True)
        self.mode_btn_nav.clicked.connect(lambda: self.switch_mode(1))
        
        # 互斥样式
        self.mode_buttons = [self.mode_btn_mapping, self.mode_btn_nav]
        
        mode_layout.addWidget(self.mode_btn_mapping)
        mode_layout.addWidget(self.mode_btn_nav)
        mode_layout.addStretch()
        
        main_layout.addLayout(mode_layout)

        # 2. 堆叠窗口区域
        self.stacked_widget = QStackedWidget()
        
        # Page 0: 绘图模式 (原有的界面)
        self.mapping_widget = QWidget()
        mapping_layout = QHBoxLayout(self.mapping_widget)
        
        # 左侧控制面板
        control_panel = self.create_control_panel()
        mapping_layout.addWidget(control_panel, 1)

        # 右侧显示面板
        display_panel = self.create_display_panel()
        mapping_layout.addWidget(display_panel, 3)
        
        self.stacked_widget.addWidget(self.mapping_widget)
        
        # Page 1: 导航模式
        self.nav_widget = NavigationModeWidget(self)
        self.stacked_widget.addWidget(self.nav_widget)
        
        main_layout.addWidget(self.stacked_widget)
        
    def switch_mode(self, index):
        """切换模式"""
        self.stacked_widget.setCurrentIndex(index)
        
        # 更新按钮状态
        for i, btn in enumerate(self.mode_buttons):
            is_selected = (i == index)
            btn.setChecked(is_selected)
            # 阻止重复点击当前模式
            if is_selected:
                btn.setEnabled(False)
            else:
                btn.setEnabled(True)
            
        if index == 1:
            # 切换到导航模式时，刷新列表
            self.nav_widget.refresh_map_list()


    def create_control_panel(self):
        """创建控制面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # ===== 区域选择 =====
        region_group = QGroupBox("1. 监控区域")
        region_layout = QVBoxLayout()

        self.select_region_btn = QPushButton("🖱️ 画框选择区域")
        self.select_region_btn.clicked.connect(self.select_region)
        region_layout.addWidget(self.select_region_btn)

        # 新增：中心点选择按钮
        self.select_center_btn = QPushButton("🎯 选择人物中心点")
        self.select_center_btn.clicked.connect(self.select_center_point)
        self.select_center_btn.setEnabled(True)  # 启用中心点选择按钮
        region_layout.addWidget(self.select_center_btn)

        # 新增：截图大小设置
        self.size_label = QLabel("截图大小:")
        region_layout.addWidget(self.size_label)

        self.size_spin = QSpinBox()
        self.size_spin.setRange(100, 1000)
        self.size_spin.setValue(200)
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

        # ===== 监控控制 =====
        monitor_group = QGroupBox("2. 监控控制")
        monitor_layout = QVBoxLayout()

        # FPS设置
        fps_layout = QHBoxLayout()
        fps_layout.addWidget(QLabel("帧率(FPS):"))
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 60)
        self.fps_spin.setValue(10) # 默认10 FPS，与原来保持一致
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

        # ===== 融合策略 =====
        merge_group = QGroupBox("3. 融合参数 (Weighted Merge)")
        merge_layout = QVBoxLayout()
        
        # 说明
        info_label = QLabel("当前采用高精度加权融合模式。\n该模式通过累积多帧置信度来消除噪音。")
        info_label.setWordWrap(True)
        merge_layout.addWidget(info_label)
        
        # 参数: 融合权重
        self.weight_label = QLabel("单帧置信度增量 (0.1-1.0):")
        merge_layout.addWidget(self.weight_label)
        self.weight_spin = QDoubleSpinBox()
        self.weight_spin.setRange(0.05, 1.0)
        self.weight_spin.setSingleStep(0.05)
        self.weight_spin.setValue(0.3)
        self.weight_spin.setToolTip("值越小越抗噪，但更新越慢；值越大更新越快，但容易引入噪音。")
        self.weight_spin.valueChanged.connect(self.update_merge_params)
        merge_layout.addWidget(self.weight_spin)
        
        merge_group.setLayout(merge_layout)
        layout.addWidget(merge_group)

        # ===== HSV参数 =====
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

        # ===== 特征参数 =====
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

        # ===== 统计信息 =====
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
        """创建显示面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # 1. 实时捕获显示
        capture_group = QGroupBox("当前视野 (实时)")
        capture_layout = QVBoxLayout()
        self.capture_label = QLabel()
        self.capture_label.setAlignment(Qt.AlignCenter)
        self.capture_label.setMinimumSize(200, 200)
        self.capture_label.setStyleSheet("background-color: black;")
        capture_layout.addWidget(self.capture_label)
        capture_group.setLayout(capture_layout)
        layout.addWidget(capture_group, 1)

        # 2. 全局地图
        self.global_group = CollapsibleMapGroup("全局拼接地图 (点击设置导航点)")
        # 获取内部的可缩放地图组件
        self.global_map_widget = self.global_group.scalable_map
        self.global_map_widget.setStyleSheet("background-color: black;")
        self.global_map_widget.pixel_clicked.connect(self.on_map_click)
        
        layout.addWidget(self.global_group, 3)

        return panel

    def _compute_scale(self):
        """计算从Qt逻辑坐标到物理像素的缩放系数"""
        screen = QApplication.primaryScreen()
        geom = screen.geometry()

        # 优先使用设备像素比
        dpr = screen.devicePixelRatio()
        if dpr > 0:
            return dpr, dpr

        # 备选：通过mss推导
        try:
            import mss
            with mss.mss() as sct:
                mon = sct.monitors[1]
                scale_x = mon["width"] / geom.width()
                scale_y = mon["height"] / geom.height()
                return scale_x, scale_y
        except:
            pass

        # 兜底：DPI比值
        logical_dpi = screen.logicalDotsPerInch() or 96.0
        physical_dpi = screen.physicalDotsPerInch() or logical_dpi
        s = physical_dpi / logical_dpi
        return s, s

    def select_region(self):
        """选择监控区域"""
        if self.overlay_active:
            print("覆盖层已在显示中")
            return

        try:
            self.overlay_active = True
            # self.overlay = TransparentOverlay() # 已在 __init__ 中初始化，此处不再重复创建

            # 连接信号
            self.overlay.region_selected.connect(self.on_region_selected)
            self.overlay.destroyed.connect(lambda: setattr(self, 'overlay_active', False))

            # 显示覆盖层
            self.overlay.showFullScreen()
            self.overlay.raise_()
            self.overlay.activateWindow()

            # 强制置顶
            self._set_topmost(self.overlay)
            self._ensure_overlay_topmost()

            print("✓ 覆盖层已显示")

        except Exception as e:
            self.overlay_active = False
            print(f"创建覆盖层错误: {e}")

    def select_center_point(self):
        """选择中心点位置"""
        if self.center_selector_active:
            print("中心选择器已在显示中")
            return

        try:
            self.center_selector_active = True
            self.center_selector = CenterPointSelector()

            # 连接信号
            self.center_selector.point_selected.connect(self.on_center_selected)
            self.center_selector.selection_cancelled.connect(self.on_center_selection_cancelled)
            self.center_selector.destroyed.connect(lambda: setattr(self, 'center_selector_active', False))

            # 显示选择器
            self.center_selector.showFullScreen()
            self.center_selector.raise_()
            self.center_selector.activateWindow()

            # 强制置顶
            self._set_topmost(self.center_selector)
            self._ensure_overlay_topmost()

            print("✓ 中心点选择器已显示")

        except Exception as e:
            self.center_selector_active = False
            print(f"创建中心选择器错误: {e}")

    def on_center_selected(self, x, y):
        """中心点选择完成"""
        # 计算缩放
        sx, sy = self._compute_scale()

        # 转换为物理像素
        px_x = int(x * sx)
        px_y = int(y * sy)

        self.monitor_center = (px_x, px_y)
        self.monitor_size = self.size_spin.value()

        self.region_label.setText(
            f"中心点: ({x}, {y})\n"
            f"物理: ({px_x}, {px_y})\n"
            f"截图大小: {self.monitor_size}x{self.monitor_size}\n"
            f"缩放: {sx:.3f}x{sy:.3f}"
        )

        self.start_btn.setEnabled(True)
        self.color_picker_btn.setEnabled(True)  # 启用颜色选择
        self.select_region_btn.setEnabled(True)   # 保持区域选择按钮可用，允许模式切换
        self.select_center_btn.setEnabled(True)  # 保持中心点选择按钮可用

        # 立即截图一次并显示
        self.capture_and_display_once()

        # 保存配置
        self.save_config()

        print(f"✓ 监控中心点已设置: ({px_x}, {px_y}), 大小: {self.monitor_size}x{self.monitor_size}")

    def on_center_selection_cancelled(self):
        """中心点选择取消"""
        self.center_selector_active = False
        print("✗ 中心点选择已取消")

    def update_capture_size(self, size):
        """更新截图大小"""
        self.monitor_size = size
        if self.monitor_center:
            # 如果已有中心点，更新显示
            cx, cy = self.monitor_center
            sx, sy = self._compute_scale()
            logical_x = int(cx / sx)
            logical_y = int(cy / sy)

            self.region_label.setText(
                f"中心点: ({logical_x}, {logical_y})\n"
                f"物理: ({cx}, {cy})\n"
                f"截图大小: {self.monitor_size}x{self.monitor_size}\n"
                f"缩放: {sx:.3f}x{sy:.3f}"
            )
            self.save_config()

    def open_color_picker(self):
        """打开颜色选择器"""
        if not self.monitor_region and not self.monitor_center:
            print("⚠️ 请先选择监控区域或中心点")
            return

        try:
            # 根据模式选择截图方式
            if self.monitor_center:
                # 使用中心点模式
                center_x, center_y = self.monitor_center
                screenshot = self.screen_capture.capture_square(center_x, center_y, self.monitor_size)
            else:
                # 使用区域模式
                screenshot = self.screen_capture.capture(
                    self.monitor_region['left'],
                    self.monitor_region['top'],
                    self.monitor_region['width'],
                    self.monitor_region['height']
                )

            # 打开颜色选择对话框（传递当前识别参数）
            current_params = self.recognizer.get_params()
            dialog = ColorPickerDialog(screenshot, self, recognizer_params=current_params)

            if dialog.exec():
                # 获取结果
                result = dialog.get_result()

                # 更新HSV范围
                if result['wall_hsv']:
                    min_hsv, max_hsv = result['wall_hsv']
                    self.recognizer.wall_hsv_min = min_hsv
                    self.recognizer.wall_hsv_max = max_hsv
                    print(f"✓ 墙体HSV已更新: {min_hsv} - {max_hsv}")

                if result['player_hsv']:
                    min_hsv, max_hsv = result['player_hsv']
                    self.recognizer.player_hsv_min = min_hsv
                    self.recognizer.player_hsv_max = max_hsv
                    print(f"✓ 人物HSV已更新: {min_hsv} - {max_hsv}")

                # 处理智能推荐 (针对彩色地图)
                if result.get('recommend_sat_filter_off', False):
                    self.recognizer.sat_filter_enabled = False
                    self.recognizer.transparent_mode = False
                    print("⚠️ [自动调整] 检测到彩色墙体：")
                    print("   1. 已关闭饱和度过滤 (sat_filter_enabled = False)")
                    print("   2. 已关闭透明地图模式 (transparent_mode = False)")

                # 保存配置
                self.save_config()

                print("✅ 颜色选择完成！")

        except Exception as e:
            print(f"颜色选择错误: {e}")
            import traceback
            traceback.print_exc()

    def on_region_selected(self, x, y, width, height):
        """区域选择完成"""
        # 计算缩放
        sx, sy = self._compute_scale()

        # 转换为物理像素
        px_left = int(x * sx)
        px_top = int(y * sy)
        px_w = int(width * sx)
        px_h = int(height * sy)

        self.monitor_region = {
            'left': px_left,
            'top': px_top,
            'width': px_w,
            'height': px_h
        }

        self.region_label.setText(
            f"逻辑: ({x}, {y}) {width}x{height}\n"
            f"物理: ({px_left}, {px_top}) {px_w}x{px_h}\n"
            f"缩放: {sx:.3f}x{sy:.3f}"
        )

        self.start_btn.setEnabled(True)
        self.color_picker_btn.setEnabled(True)  # 启用颜色选择
        self.select_center_btn.setEnabled(True)  # 启用中心点选择按钮，允许模式切换
        self.select_region_btn.setEnabled(True)  # 启用区域选择按钮

        # 立即截图一次并显示 ⭐ 新增
        self.capture_and_display_once()

        # 保存配置
        self.save_config()

        print(f"✓ 监控区域已设置: ({px_left}, {px_top}) {px_w}x{px_h}")

    def toggle_monitoring(self):
        """开始/停止监控"""
        if self.monitoring:
            self.monitoring = False
            self.capture_timer.stop()
            self.start_btn.setText("▶️ 开始监控")
            self.stats_text.append("监控已停止。")
        else:
            if not self.monitor_center and not self.monitor_region:
                QMessageBox.warning(self, "提示", "请先选择一个监控区域或中心点。")
                return

            self.monitoring = True
            fps = self.fps_spin.value()
            self.capture_timer.start(1000 // fps)
            self.start_btn.setText("⏸️ 停止监控")
            self.stats_text.append("监控已开始...")

    def reset_map(self):
        """重置地图和追踪器"""
        if self.monitoring:
            self.toggle_monitoring() # 先停止监控

        self.stitcher = MapStitcher(canvas_size=5000)
        self.tracker = PlayerTracker()
        self.global_map_widget.clear_map()
        self.stats_text.append("地图和追踪器已重置。")
        print("Map and tracker have been reset.")

    def save_map(self):
        """保存拼接的地图及相关数据"""
        if self.monitoring:
            self.toggle_monitoring()

        map_name, ok = QInputDialog.getText(self, '保存地图', '请输入地图名称:')
        if not ok or not map_name:
            return

        try:
            # 1. 创建目录
            base_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "map_data")
            map_folder = os.path.join(base_path, map_name)
            os.makedirs(map_folder, exist_ok=True)

            # 2. 保存地图和掩码
            map_path = os.path.join(map_folder, "map.png")
            mask_path = os.path.join(map_folder, "mask.png")
            cv2.imwrite(map_path, self.stitcher.canvas)
            cv2.imwrite(mask_path, self.stitcher.walkable_mask)

            # 3. 保存元数据
            metadata_path = os.path.join(map_folder, "metadata.npz")
            self.stitcher.save_metadata(metadata_path)

            # 4. 创建并保存 config.json
            config_path = os.path.join(map_folder, "config.json")
            
            config_data = {
                "draw_scale": self.stitcher.draw_scale,
                "monitor_center": self.monitor_center,
                "monitor_size": self.monitor_size,
                "recognizer_params": self.recognizer.get_params(),
                "nav_preferences": {
                    "k_ratio": 10.0, # 默认值
                    "y_bias": 1.0,   # 默认值
                    "center_offset_y": 0 # 默认值
                }
            }

            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)

            QMessageBox.information(self, "成功", f"地图 '{map_name}' 已成功保存！")
            self.stats_text.append(f"地图 '{map_name}' 已保存。")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存地图失败: {e}")
            self.stats_text.append(f"保存地图失败: {e}")

    def capture_and_display_once(self):
        """立即捕获并显示一次（用于区域选择后预览）"""
        if not self.monitor_region and not self.monitor_center:
            return

        try:
            # 根据模式选择截图方式
            if self.monitor_center:
                # 使用中心点模式
                center_x, center_y = self.monitor_center
                img = self.screen_capture.capture_square(center_x, center_y, self.monitor_size)
            else:
                # 使用区域模式
                img = self.screen_capture.capture(
                    self.monitor_region['left'],
                    self.monitor_region['top'],
                    self.monitor_region['width'],
                    self.monitor_region['height']
                )

            # HSV识别
            combined, wall_mask, fog_mask = self.recognizer.extract_combined(img)

            # 获取预处理后的图像（用于显示，确保与颜色选择器一致）
            img_processed = self.recognizer.get_preprocessed_image(img)

            # 只更新统计信息，不显示当前捕获（因为UI中已移除）
            print("✓ 已截图预览（功能正常，仅UI隐藏）")

        except Exception as e:
            print(f"截图预览错误: {e}")

    def toggle_monitoring(self):
        """切换监控状态"""
        if not self.monitoring:
            self.monitoring = True
            self.start_btn.setText("⏸️ 停止监控")
            self.select_region_btn.setEnabled(False)
            self.fps_spin.setEnabled(False)  # 锁定FPS设置

            # 启动定时器，使用用户设置的FPS
            fps = self.fps_spin.value()
            interval = int(1000 / fps)
            self.capture_timer.start(interval)

            print(f"✓ 开始监控 (FPS: {fps})...")
        else:
            self.monitoring = False
            self.start_btn.setText("▶️ 开始监控")
            self.select_region_btn.setEnabled(True)
            self.fps_spin.setEnabled(True)  # 解锁FPS设置

            self.capture_timer.stop()

            print("✓ 监控已停止")

    def capture_and_process(self):
        """捕获并处理（核心循环）- 保留所有功能，只是不显示当前捕获"""
        if not self.monitor_region and not self.monitor_center:
            return

        try:
            # 1. 捕获屏幕
            if self.monitor_center:
                # 使用中心点模式
                center_x, center_y = self.monitor_center
                img = self.screen_capture.capture_square(center_x, center_y, self.monitor_size)

                # 在中心点模式下，玩家位置就是图像中心
                player_pos = (self.monitor_size // 2, self.monitor_size // 2)
            else:
                # 使用区域模式
                img = self.screen_capture.capture(
                    self.monitor_region['left'],
                    self.monitor_region['top'],
                    self.monitor_region['width'],
                    self.monitor_region['height']
                )

                # 识别玩家位置 (px, py)
                # 使用 extract_player 提取玩家 mask，然后用 tracker 计算中心
                player_mask = self.recognizer.extract_player(img)
                player_pos = self.tracker.detect_player(player_mask)

            # 2. HSV识别（二值化）
            # 关键修改：传入 player_pos，确保掩盖正确的玩家中心
            combined, wall_mask, fog_mask = self.recognizer.extract_combined(img, player_pos=player_pos)

            # 获取预处理后的图像（用于显示，确保与颜色选择器一致）
            img_processed = self.recognizer.get_preprocessed_image(img)

            # 获取原始灰度图（包含丰富纹理，用于特征匹配）
            # 使用 recognizer 提供的 get_raw_gray，确保应用了相同的图像增强（CLAHE等）
            raw_gray = self.recognizer.get_raw_gray(img)

            # 3. 添加到拼接器
            # 关键修改：传入 raw_gray 用于位移计算，combined 用于地图绘制，player_pos 用于对齐
            self.stitcher.add_frame(img, combined, wall_mask, fog_mask, raw_gray=raw_gray, player_pos=player_pos)

            # 4. 更新显示（只更新全局地图，移除了当前捕获显示）
            self.update_displays(img_processed, combined)

            # 5. 更新统计
            self.update_statistics()

        except Exception as e:
            print(f"处理错误: {e}")

    def update_displays(self, current_img, combined_mask):
        """更新显示"""
        # 1. 显示当前捕获（处理后的图像）
        # 将 combined_mask 叠加在原图上显示，方便观察识别效果
        display_img = current_img.copy()
        
        # 提取墙壁轮廓并绘制成红色
        contours, _ = cv2.findContours(combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(display_img, contours, -1, (0, 0, 255), 1)
        
        self._show_image(self.capture_label, display_img)

        # 2. 全局地图（显示完整探索地图 + 视野框）
        # 获取当前位置
        current_x, current_y = self.stitcher.get_current_position()

        # 获取增强后的地图（墙体强化+背景弱化）
        if hasattr(self.stitcher, 'get_enhanced_map'):
            # 新版接口，返回 (image, offset)
            result = self.stitcher.get_enhanced_map(margin=500)
            if isinstance(result, tuple):
                global_map, (crop_x1, crop_y1) = result
            else:
                # 兼容旧接口（虽然应该不会走到这里）
                global_map = result
                # 兜底计算
                coords = cv2.findNonZero(self.stitcher.canvas)
                if coords is not None:
                    x, y, w_map, h_map = cv2.boundingRect(coords)
                    crop_x1 = max(0, x - 500)
                    crop_y1 = max(0, y - 500)
                else:
                    crop_x1, crop_y1 = 0, 0
        else:
            global_map = self.stitcher.get_cropped_map(margin=500)
            # 旧版逻辑
            coords = cv2.findNonZero(self.stitcher.canvas)
            if coords is not None:
                x, y, w_map, h_map = cv2.boundingRect(coords)
                crop_x1 = max(0, x - 500)
                crop_y1 = max(0, y - 500)
            else:
                crop_x1, crop_y1 = 0, 0

        if global_map.size > 0:
            # 转彩色
            global_colored = cv2.cvtColor(global_map, cv2.COLOR_GRAY2BGR)

            # 记录偏移量用于点击映射
            self.map_crop_offset = (crop_x1, crop_y1)

            # 绘制导航路径
            if self.nav_path:
                points_to_draw = []
                for px, py in self.nav_path:
                    local_px = px - crop_x1
                    local_py = py - crop_y1
                    # 只绘制在裁剪区域内的点（简单的边界检查交给OpenCV）
                    points_to_draw.append([local_px, local_py])

                if len(points_to_draw) > 1:
                    cv2.polylines(global_colored, [np.array(points_to_draw)], False, (0, 255, 255), 2)
                    # 画终点
                    dest = points_to_draw[-1]
                    cv2.circle(global_colored, tuple(dest), 6, (0, 0, 255), -1)
                    cv2.circle(global_colored, tuple(dest), 8, (255, 255, 255), 1)

            # 当前位置在裁剪地图上的坐标
            fov_x = int(current_x - crop_x1)
            fov_y = int(current_y - crop_y1)

            # 视野框大小（当前捕获的尺寸）
            fov_w, fov_h = current_img.shape[1], current_img.shape[0]

            # 画视野框（绿色）
            cv2.rectangle(
                global_colored,
                (fov_x - fov_w // 2, fov_y - fov_h // 2),
                (fov_x + fov_w // 2, fov_y + fov_h // 2),
                (0, 255, 0), 3
            )

            # 画中心点
            cv2.circle(global_colored, (fov_x, fov_y), 8, (0, 255, 0), -1)
            cv2.circle(global_colored, (fov_x, fov_y), 10, (0, 255, 0), 2)

            # 转换为QPixmap并显示在可缩放地图组件中
            h, w = global_colored.shape[:2]
            if h > 0 and w > 0:
                # 限制显示分辨率，防止UI卡顿或内存溢出
                # 如果图像过大，进行缩放用于显示（保存时依然是原图）
                max_display_dim = 4096
                display_scale = 1.0
                
                if h > max_display_dim or w > max_display_dim:
                    display_scale = min(max_display_dim / h, max_display_dim / w)
                    new_w = int(w * display_scale)
                    new_h = int(h * display_scale)
                    global_colored_display = cv2.resize(global_colored, (new_w, new_h), interpolation=cv2.INTER_NEAREST)
                else:
                    global_colored_display = global_colored

                # 确保数据连续且对齐
                if not global_colored_display.flags['C_CONTIGUOUS']:
                    global_colored_display = np.ascontiguousarray(global_colored_display)

                h_disp, w_disp = global_colored_display.shape[:2]
                rgb = cv2.cvtColor(global_colored_display, cv2.COLOR_BGR2RGB)
                bytes_per_line = 3 * w_disp
                q_img = QImage(rgb.data, w_disp, h_disp, bytes_per_line, QImage.Format_RGB888)
                
                # 必须使用copy()，否则QImage引用的数据可能会被垃圾回收或修改
                pixmap = QPixmap.fromImage(q_img.copy())

                # 设置到可缩放地图组件
                self.global_map_widget.set_image(pixmap)

    def on_map_click(self, x, y):
        """处理地图点击，进行寻路"""
        if not self.map_crop_offset:
            return

        crop_x1, crop_y1 = self.map_crop_offset
        global_x = x + crop_x1
        global_y = y + crop_y1

        print(f"📍 导航目标: ({global_x}, {global_y})")

        start_pos = (self.stitcher.current_x, self.stitcher.current_y)
        end_pos = (global_x, global_y)

        # 计算路径
        # 注意：这里直接在UI线程计算，如果地图非常大可能需要放到线程中
        # 但目前的降采样算法非常快(0.1s)，直接运行即可
        self.nav_path = self.path_finder.find_path(self.stitcher.wall_layer, start_pos, end_pos)

        if self.nav_path:
            print(f"✅ 路径已生成，包含 {len(self.nav_path)} 个节点")
        else:
            print("❌ 无法找到路径（可能目标在墙内或不可达）")

    def _show_image(self, label, img):
        """将OpenCV图像显示在QLabel上"""
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        q_img = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        label.setPixmap(QPixmap.fromImage(q_img))

    def update_statistics(self):
        """更新统计信息"""
        stats = self.stitcher.get_statistics()

        text = f"""
总帧数: {stats['total_frames']}
成功匹配: {stats['successful_matches']}
失败匹配: {stats['failed_matches']}
匹配率: {stats['match_rate']:.1f}%
匹配质量: {stats['match_quality']:.2f}
平均位移: {stats['avg_displacement']:.2f}
探索进度: {stats['exploration']:.4f}%
        """

        self.stats_text.setText(text.strip())

    def update_hsv_params(self):
        """更新HSV参数"""
        self.recognizer.enable_wall = self.wall_check.isChecked()
        self.recognizer.enable_fog = self.fog_check.isChecked()

    def update_feature_params(self):
        """更新特征参数"""
        params = {
            'clahe_enabled': self.clahe_check.isChecked(),
            'deepen_enabled': self.deepen_check.isChecked(),
            'wall_weight': self.wall_weight_spin.value(),
            'edge_weight': self.edge_weight_spin.value(),
            'gray_weight': self.gray_weight_spin.value(),
            'edge_low': self.canny_low_spin.value(),
            'edge_high': self.canny_high_spin.value()
        }
        self.recognizer.set_params(params)
        self.save_config()

    def update_merge_params(self):
        """更新融合参数"""
        weight = self.weight_spin.value()
        self.stitcher.weight_add = weight
        print(f"融合置信度增量: {weight}")

    def open_advanced_settings(self):
        """打开高级设置"""
        try:
            # 获取当前参数 (识别器 + 拼接器)
            current_params = self.recognizer.get_params()
            stitcher_params = self.stitcher.get_params()
            
            # 合并参数
            current_params.update(stitcher_params)

            dialog = AdvancedSettingsDialog(self, current_params)

            if dialog.exec():
                new_params = dialog.get_params()
                self.recognizer.set_params(new_params)
                self.stitcher.set_params(new_params)

                print("✅ 高级参数已更新")
                # 保存配置
                self.save_config()
        except Exception as e:
            print(f"高级设置错误: {e}")
            import traceback
            traceback.print_exc()

    def reset_map(self):
        """重置地图"""
        self.stitcher.reset()
        self.tracker.reset()
        # 清空可缩放地图组件
        if self.global_map_widget:
            self.global_map_widget.set_image(None)
        self.stats_text.clear()
        print("✓ 地图已重置")

    def save_map(self):
        """保存地图 (新版：保存为数据包 + 配置文件)"""
        from PySide6.QtWidgets import QInputDialog, QMessageBox
        import os
        import json

        # 让用户输入地图名称
        text, ok = QInputDialog.getText(self, "保存地图", "请输入地图名称 (将作为文件夹名):")
        if ok and text:
            # 简单的名称净化
            safe_name = "".join([c for c in text if c.isalpha() or c.isdigit() or c in (' ', '_', '-')]).strip()
            if not safe_name:
                safe_name = "unnamed_map"
            
            # 创建路径: ./map_data/<safe_name>
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir) # 回退一级到项目根目录
            map_data_dir = os.path.join(project_root, "map_data")
            save_path = os.path.join(map_data_dir, safe_name)
            
            # 确保父目录存在
            if not os.path.exists(map_data_dir):
                os.makedirs(map_data_dir)
            
            # 调用 Stitcher 的保存功能 (只保存数据)
            try:
                self.stitcher.save_map_package(save_path)
                
                # --- 保存配置文件 config.json ---
                try:
                    config = {
                        # 1. 监视器配置 (最关键)
                        "monitor_mode": "center" if self.monitor_center else "region",
                        "monitor_center": list(self.monitor_center) if self.monitor_center else None,
                        "monitor_size": self.monitor_size,
                        "monitor_region": list(self.monitor_region) if self.monitor_region else None,
                        
                        # 2. 拼接器参数
                        "canvas_size": self.stitcher.canvas_size,
                        "draw_scale": self.stitcher.draw_scale,
                        "stitcher_params": self.stitcher.get_params(),
                        
                        # 3. 图像识别参数
                        "recognizer_params": self.recognizer.get_params(), # 需确保 Recognizer 有此方法
                        
                        # 4. 导航偏好 (新增，从 NavigationWidget 获取，如果已初始化)
                        # 如果当前还没打开过导航模式，就用默认值
                        "nav_preferences": {
                            "k_ratio": 10.0,
                            "y_bias": 1.0,
                            "center_offset_y": 0
                        }
                    }
                    
                    # 尝试获取当前的导航参数（如果存在）
                    if hasattr(self, 'nav_widget'):
                        config["nav_preferences"] = {
                            "k_ratio": self.nav_widget.nav_k_ratio_spin.value(),
                            "y_bias": self.nav_widget.nav_y_bias_spin.value(),
                            "center_offset_y": self.nav_widget.nav_center_offset_spin.value()
                        }
                    
                    config_path = os.path.join(save_path, "config.json")
                    with open(config_path, 'w', encoding='utf-8') as f:
                        json.dump(config, f, indent=4, ensure_ascii=False)
                    print(f"配置文件已保存: {config_path}")
                    
                except Exception as conf_err:
                    print(f"保存配置文件失败: {conf_err}")
                    QMessageBox.warning(self, "警告", f"地图数据已保存，但配置文件保存失败:\n{conf_err}")
                
                # 额外逻辑：由UI层负责保存预览图片
                try:
                    # 获取增强后的地图（墙体强化+背景弱化）
                    result = self.stitcher.get_enhanced_map(margin=50)
                    if isinstance(result, tuple):
                        global_map, _ = result
                    else:
                        global_map = result
                        
                    if global_map is not None and global_map.size > 0:
                        image_path = os.path.join(save_path, "map_image.png")
                        # 修复：使用 imencode 处理中文路径
                        is_success, im_buf = cv2.imencode(".png", global_map)
                        if is_success:
                            im_buf.tofile(image_path)
                            print(f"预览图片已保存: {image_path}")
                        else:
                            print("图片编码失败")
                except Exception as img_err:
                    print(f"保存预览图片失败: {img_err}")

                # 提示成功
                QMessageBox.information(self, "保存成功", f"地图及配置已保存至:\n{save_path}")
                
                # 如果导航模式已初始化，刷新列表
                if hasattr(self, 'nav_widget'):
                    self.nav_widget.refresh_map_list()
                    
            except Exception as e:
                print(f"保存失败: {e}")
                QMessageBox.critical(self, "保存失败", f"无法保存地图:\n{str(e)}")

    def save_config(self):
        """保存配置"""
        config = {
            '监控区域': self.monitor_region,
            '监控中心': self.monitor_center,
            '监控大小': self.monitor_size,
            'FPS': self.fps_spin.value(),  # 保存FPS设置
            '特征参数': {
                'clahe_enabled': self.clahe_check.isChecked(),
                'wall_weight': self.wall_weight_spin.value(),
                'edge_weight': self.edge_weight_spin.value(),
                'gray_weight': self.gray_weight_spin.value(),
                'edge_low': self.canny_low_spin.value(),
                'edge_high': self.canny_high_spin.value(),
                'transparent_mode': self.recognizer.transparent_mode,
                'trans_wall_thresh': self.recognizer.trans_wall_thresh
            },
            '融合策略': {
                'weight': self.weight_spin.value()
            },
            '保存时间': datetime.now().isoformat()
        }

        try:
            with open('config.json', 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存配置失败: {e}")

    def load_saved_params(self):
        """加载保存的参数"""
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)

            # 加载特征参数
            params = config.get('特征参数', {})
            if params:
                self.clahe_check.setChecked(params.get('clahe_enabled', False))
                self.wall_weight_spin.setValue(params.get('wall_weight', 50))
                self.edge_weight_spin.setValue(params.get('edge_weight', 30))
                self.gray_weight_spin.setValue(params.get('gray_weight', 20))
                self.canny_low_spin.setValue(params.get('edge_low', 50))
                self.canny_high_spin.setValue(params.get('edge_high', 150))

                self.recognizer.set_params(params)

                print("✓ 已加载保存的参数")

            # 加载融合策略
            merge_params = config.get('融合策略', {})
            if merge_params:
                self.weight_spin.setValue(merge_params.get('weight', 0.3))

            # 加载FPS设置
            fps = config.get('FPS', 10)  # 默认10 FPS
            self.fps_spin.setValue(fps)

            # 加载监控区域或中心点
            monitor_region = config.get('监控区域')
            monitor_center = config.get('监控中心')
            monitor_size = config.get('监控大小', 200)

            if monitor_center:
                self.monitor_center = monitor_center
                self.monitor_size = monitor_size

                # 计算缩放
                sx, sy = self._compute_scale()
                logical_x = int(monitor_center[0] / sx)
                logical_y = int(monitor_center[1] / sy)

                self.region_label.setText(
                    f"中心点: ({logical_x}, {logical_y})\n"
                    f"物理: ({monitor_center[0]}, {monitor_center[1]})\n"
                    f"截图大小: {monitor_size}x{monitor_size}\n"
                    f"缩放: {sx:.3f}x{sy:.3f}"
                )

                self.start_btn.setEnabled(True)
                self.color_picker_btn.setEnabled(True)
                self.select_region_btn.setEnabled(True)   # 保持区域选择按钮可用，允许模式切换
                self.select_center_btn.setEnabled(True)  # 保持中心点选择按钮可用

                print(f"✓ 已加载监控中心点: {monitor_center}, 大小: {monitor_size}")

            elif monitor_region:
                self.monitor_region = monitor_region

                # 更新UI显示
                left = monitor_region['left']
                top = monitor_region['top']
                width = monitor_region['width']
                height = monitor_region['height']

                # 计算逻辑坐标
                sx, sy = self._compute_scale()
                logical_left = int(left / sx)
                logical_top = int(top / sy)
                logical_width = int(width / sx)
                logical_height = int(height / sy)

                self.region_label.setText(
                    f"逻辑: ({logical_left}, {logical_top}) {logical_width}x{logical_height}\n"
                    f"物理: ({left}, {top}) {width}x{height}\n"
                    f"缩放: {sx:.3f}x{sy:.3f}"
                )

                self.start_btn.setEnabled(True)
                self.color_picker_btn.setEnabled(True)
                self.select_center_btn.setEnabled(True)   # 保持中心点选择按钮可用，允许模式切换
                self.select_region_btn.setEnabled(True)  # 保持区域选择按钮可用

                print(f"✓ 已加载监控区域: {monitor_region}")

        except Exception as e:
            print(f"加载配置失败: {e}")
            pass

    def _set_topmost(self, widget):
        """使用Windows API将窗口设为Topmost"""
        try:
            hwnd = int(widget.winId())
            user32 = ctypes.windll.user32
            HWND_TOPMOST = -1
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_NOACTIVATE = 0x0010
            SWP_SHOWWINDOW = 0x0040
            flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW
            user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, flags)
        except:
            pass

    def _ensure_overlay_topmost(self):
        """定时维持覆盖层为顶层"""
        try:
            if not hasattr(self, "_overlay_topmost_timer"):
                self._overlay_topmost_timer = QTimer(self)
                self._overlay_topmost_timer.setInterval(500)

                def tick():
                    if hasattr(self, 'overlay') and self.overlay and self.overlay.isVisible():
                        self._set_topmost(self.overlay)
                    else:
                        self._overlay_topmost_timer.stop()

                self._overlay_topmost_timer.timeout.connect(tick)

            self._overlay_topmost_timer.start()
        except:
            pass

    def update_topmost(self):
        """更新窗口置顶状态"""
        if self.topmost_check.isChecked():
            self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
            self.show()
            self._set_topmost(self)
        else:
            self.setWindowFlag(Qt.WindowStaysOnTopHint, False)
            self.show()

    def update_overlay_for_nav(self, center_x, center_y, size):
        """在导航模式下更新黄框预览"""
        # 确保 overlay 存在
        if not hasattr(self, 'overlay') or not self.overlay:
            self.overlay = TransparentOverlay()

        # 设置为非交互模式，并禁用背景
        self.overlay.set_interactive(False)
        self.overlay.set_draw_background(False)
        
        if not self.overlay.isVisible():
            self.overlay.show()
        
        # 计算左上角坐标
        x = center_x - size // 2
        y = center_y - size // 2
        
        # 更新 overlay 的位置和大小
        self.overlay.setGeometry(x, y, size, size)
        
        # 在非交互模式下，我们需要自己绘制一个矩形来代替用户绘制
        self.overlay.start_point = QPoint(x, y)
        self.overlay.end_point = QPoint(x + size, y + size)
        self.overlay.drawing = False # 表示绘制完成
        self.overlay.update() # 触发重绘