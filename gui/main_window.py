"""
主窗口
集成所有功能：区域选择、实时监控、地图拼接、参数调整
"""

import sys
import json
import ctypes
from datetime import datetime

import cv2
import numpy as np
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QGroupBox, QCheckBox,
    QSpinBox, QTextEdit, QApplication, QComboBox, QDoubleSpinBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap

from core import ScreenCapture, HSVRecognizer, MapStitcher, PlayerTracker
from core.pathfinder import PathFinder
from .overlay import TransparentOverlay
from .center_selector import CenterPointSelector
from .color_picker import ColorPickerDialog
from .widgets import ClickableImageLabel, CollapsibleMapGroup


class MainWindow(QMainWindow):
    """实时小地图监控主窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("实时小地图拼接系统")
        self.setGeometry(100, 100, 1400, 900)
        
        # 设置窗口始终保持在最顶层
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        
        # 核心组件
        self.screen_capture = ScreenCapture()
        self.recognizer = HSVRecognizer()
        self.stitcher = MapStitcher(canvas_size=6000)
        self.tracker = PlayerTracker()  # 初始化追踪器
        self.path_finder = PathFinder() # 初始化寻路器
        # 启用全局修复功能


        # 监控状态
        self.monitor_region = None
        self.monitor_center = None  # 新增：中心点坐标
        self.monitor_size = 200     # 新增：截图大小，默认200x200
        self.monitoring = False
        self.overlay_active = False
        self.center_selector_active = False  # 新增：中心选择器状态

        # 导航路径
        self.nav_path = None
        
        # 定时器
        self.capture_timer = QTimer()
        self.capture_timer.timeout.connect(self.capture_and_process)
        
        # 界面
        self.setup_ui()
        
        # 加载保存的参数
        self.load_saved_params()
    
    def setup_ui(self):
        """设置界面"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        
        # 左侧控制面板
        control_panel = self.create_control_panel()
        main_layout.addWidget(control_panel, 1)
        
        # 右侧显示面板
        display_panel = self.create_display_panel()
        main_layout.addWidget(display_panel, 3)
    
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
        self.fps_spin.setValue(30) # 默认提升到30
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
        merge_group = QGroupBox("3. 墙体融合策略 (解决变胖)")
        merge_layout = QVBoxLayout()
        
        # 模式选择
        merge_layout.addWidget(QLabel("融合模式:"))
        self.merge_mode_combo = QComboBox()
        self.merge_mode_combo.addItems([
            "智能抑制 (推荐)", 
            "骨架化 (极细)", 
            "加权平均 (抗噪)"
        ])
        self.merge_mode_combo.currentIndexChanged.connect(self.update_merge_mode)
        merge_layout.addWidget(self.merge_mode_combo)
        
        # 参数: 抑制半径
        self.radius_label = QLabel("抑制半径 (px):")
        merge_layout.addWidget(self.radius_label)
        self.radius_spin = QSpinBox()
        self.radius_spin.setRange(1, 20)
        self.radius_spin.setValue(5)
        self.radius_spin.valueChanged.connect(self.update_merge_params)
        merge_layout.addWidget(self.radius_spin)
        
        # 参数: 融合权重
        self.weight_label = QLabel("融合权重增量 (0-1):")
        merge_layout.addWidget(self.weight_label)
        self.weight_spin = QDoubleSpinBox()
        self.weight_spin.setRange(0.01, 1.0)
        self.weight_spin.setSingleStep(0.05)
        self.weight_spin.setValue(0.2)
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
        """创建显示面板 - 移除当前捕获UI窗口，只保留全局地图"""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # 全局地图 - 现在占据全部显示空间
        self.global_group = CollapsibleMapGroup("全局拼接地图 (点击设置导航点)")
        self.global_group.setMinimumSize(800, 600)  # 增加默认大小

        # 获取内部的可缩放地图组件
        self.global_map_widget = self.global_group.scalable_map
        self.global_map_widget.setStyleSheet("background-color: black;")
        self.global_map_widget.pixel_clicked.connect(self.on_map_click)

        layout.addWidget(self.global_group)

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
            self.overlay = TransparentOverlay()

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

            print("√ 覆盖层已显示")

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

            print("√ 中心点选择器已显示")

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

        print(f"√ 监控中心点已设置: ({px_x}, {px_y}), 大小: {self.monitor_size}x{self.monitor_size}")

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
                    print(f"√ 墙体HSV已更新: {min_hsv} - {max_hsv}")

                if result['player_hsv']:
                    min_hsv, max_hsv = result['player_hsv']
                    self.recognizer.player_hsv_min = min_hsv
                    self.recognizer.player_hsv_max = max_hsv
                    print(f"√ 人物HSV已更新: {min_hsv} - {max_hsv}")

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

        print(f"√ 监控区域已设置: ({px_left}, {px_top}) {px_w}x{px_h}")
    
    def capture_and_display_once(self):
        """立即捕获并显示一次（用于区域选择后预览）- 移除UI显示，只保留功能"""
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

            # 功能保留，但不再显示当前捕获（因为UI元素已移除）
            print("√ 已截图预览（功能正常，仅UI隐藏）")

        except Exception as e:
            print(f"截图预览错误: {e}")

    def toggle_monitoring(self):
        """切换监控状态"""
        if not self.monitoring:
            self.monitoring = True
            self.start_btn.setText("⏸️ 停止监控")
            self.select_region_btn.setEnabled(False)
            self.fps_spin.setEnabled(False) # 锁住FPS
            
            # 启动定时器
            fps = self.fps_spin.value()
            interval = int(1000 / fps)
            self.capture_timer.start(interval)
            
            print(f"√ 开始监控 (FPS: {fps})...")
        else:
            self.monitoring = False
            self.start_btn.setText("▶️ 开始监控")
            self.select_region_btn.setEnabled(True)
            self.fps_spin.setEnabled(True)
            
            self.capture_timer.stop()
            
            print("√ 监控已停止")
    
    def capture_and_process(self):
        """捕获并处理（核心循环）"""
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
            combined, wall_mask, fog_mask = self.recognizer.extract_combined(img)

            # 获取预处理后的图像（用于显示，确保与颜色选择器一致）
            img_processed = self.recognizer.get_preprocessed_image(img)

            # 获取原始灰度图（包含丰富纹理，用于特征匹配）
            # 使用 recognizer 提供的 get_raw_gray，确保应用了相同的图像增强（CLAHE等）
            raw_gray = self.recognizer.get_raw_gray(img)

            # 3. 添加到拼接器
            # 关键修改：传入 raw_gray 用于位移计算，combined 用于地图绘制，player_pos 用于对齐
            self.stitcher.add_frame(img, combined, wall_mask, fog_mask, raw_gray=raw_gray, player_pos=player_pos)

            # 4. 更新显示
            # 关键：显示预处理后的图像，与颜色选择器保持一致
            self.update_displays(img_processed, combined)

            # 5. 更新统计
            self.update_statistics()

        except Exception as e:
            print(f"处理错误: {e}")
    
    def update_displays(self, current_img, combined_mask):
        """更新显示 - 移除当前捕获显示，只更新全局地图"""
        # ===== 全局地图（显示完整探索地图 + 视野框） =====
        # 获取当前位置
        current_x, current_y = self.stitcher.get_current_position()

        # 获取增强后的地图（使用后处理优化）
        global_map = self.stitcher.get_enhanced_map(margin=500)

        if global_map.size > 0:
            # 转彩色
            global_colored = cv2.cvtColor(global_map, cv2.COLOR_GRAY2BGR)

            # 计算视野框在裁剪地图上的位置
            # 需要获取裁剪偏移量
            coords = cv2.findNonZero(self.stitcher.canvas)
            if coords is not None:
                x, y, w_map, h_map = cv2.boundingRect(coords)
                margin = 500
                crop_x1 = max(0, x - margin)
                crop_y1 = max(0, y - margin)

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
                # 转换为QPixmap
                rgb = cv2.cvtColor(global_colored, cv2.COLOR_BGR2RGB)
                bytes_per_line = 3 * w
                q_img = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
                pixmap = QPixmap.fromImage(q_img)

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
平均位移: {stats['avg_displacement']:.2f} 像素
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

    def update_merge_mode(self, index):
        """更新融合模式"""
        modes = ['smart_v2', 'skeleton', 'weighted']
        if 0 <= index < len(modes):
            mode = modes[index]
            self.stitcher.set_merge_mode(mode)
            
            # 更新UI状态
            is_smart = (mode == 'smart_v2')
            is_weighted = (mode == 'weighted')
            
            self.radius_spin.setEnabled(is_smart)
            self.radius_label.setEnabled(is_smart)
            self.weight_spin.setEnabled(is_weighted)
            self.weight_label.setEnabled(is_weighted)
            
            print(f"模式切换: {mode}")

    def update_merge_params(self):
        """更新融合参数"""
        radius = self.radius_spin.value()
        weight = self.weight_spin.value()
        
        self.stitcher.set_merge_mode(
            self.stitcher.merge_mode, 
            radius=radius,
            weight_add=weight
        )

    def open_advanced_settings(self):
        """打开高级设置"""
        from .advanced_settings import AdvancedSettingsDialog

        try:
            # 获取当前参数
            current_params = self.recognizer.get_params()
            
            # 添加透明模式相关参数
            current_params['transparent_mode'] = self.recognizer.transparent_mode
            current_params['trans_wall_thresh'] = self.recognizer.trans_wall_thresh
            
            dialog = AdvancedSettingsDialog(self, current_params)
            
            if dialog.exec():
                new_params = dialog.get_params()
                self.recognizer.set_params(new_params)
                
                # 更新透明模式参数
                if 'transparent_mode' in new_params:
                    self.recognizer.transparent_mode = bool(new_params['transparent_mode'])
                if 'trans_wall_thresh' in new_params:
                    self.recognizer.trans_wall_thresh = int(new_params['trans_wall_thresh'])
                
                print("✅ 高级参数已更新")
                # 保存配置
                self.save_config()
        except Exception as e:
            print(f"高级设置错误: {e}")

    def reset_map(self):
        """重置地图"""
        self.stitcher.reset()
        self.tracker.reset()
        # 清空可缩放地图组件
        if self.global_map_widget:
            self.global_map_widget.set_image(None)
        self.stats_text.clear()
        print("√ 地图已重置")
    
    def save_map(self):
        """保存地图"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"map_{timestamp}.png"
        
        global_map = self.stitcher.get_cropped_map()
        cv2.imwrite(filename, global_map)
        
        print(f"💾 地图已保存: {filename}")
    
    def save_config(self):
        """保存配置"""
        config = {
            '监控区域': self.monitor_region,
            '监控中心': self.monitor_center,
            '监控大小': self.monitor_size,
            'FPS': self.fps_spin.value(), # 保存FPS
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
                'mode_index': self.merge_mode_combo.currentIndex(),
                'radius': self.radius_spin.value(),
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

                print("√ 已加载保存的参数")

            # 加载融合策略
            merge_params = config.get('融合策略', {})
            if merge_params:
                self.merge_mode_combo.setCurrentIndex(merge_params.get('mode_index', 0))
                self.radius_spin.setValue(merge_params.get('radius', 5))
                self.weight_spin.setValue(merge_params.get('weight', 0.2))

            # 加载监控区域或中心点
            monitor_region = config.get('监控区域')
            monitor_center = config.get('监控中心')
            monitor_size = config.get('监控大小', 200)

            if monitor_center:
                self.monitor_center = monitor_center
                self.monitor_size = monitor_size

                # 加载FPS
                fps = config.get('FPS', 30)
                self.fps_spin.setValue(fps)

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

                print(f"√ 已加载监控中心点: {monitor_center}, 大小: {monitor_size}")

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

                print(f"√ 已加载监控区域: {monitor_region}")

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