"""
交互式颜色选择工具 v2.1
核心修复：100%准确的坐标映射（显示坐标 → 原始图像坐标）
"""

import cv2
import numpy as np
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QGroupBox, QTextEdit, QScrollArea, QSlider
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPixmap, QMouseEvent, QPainter, QColor, QPen

from core.recognizer_optimized import HSVRecognizer
from ..widgets.clickable_label import ClickableImageLabel


class ColorPickerDialog(QDialog):
    """颜色选择对话框"""
    
    def __init__(self, screenshot, parent=None, recognizer_params=None):
        super().__init__(parent)
        self.setWindowTitle("交互式颜色选择 - 点击墙体和人物获取颜色")
        self.resize(1000, 700)
        
        # 原始截图
        self.screenshot = screenshot.copy()
        self.original_height, self.original_width = screenshot.shape[:2]
        
        # 初始化识别器并应用参数
        self.recognizer = HSVRecognizer()
        if recognizer_params:
            self.recognizer.set_params(recognizer_params)
           
            
        # 预处理图像（深化处理）
        self.processed_screenshot = self.recognizer.preprocess_image(self.screenshot)
        
      
        
        # 确保processed_screenshot存在
        if not hasattr(self, 'processed_screenshot') or self.processed_screenshot is None:
          
            self.processed_screenshot = self.screenshot.copy()
        
        # 点击的像素点（原始图像坐标）
        self.wall_points = []  # 墙体点
        self.player_points = []  # 人物点
        
        # 当前模式
        self.current_mode = 'wall'  # 'wall' or 'player'
        self.zoom = 1.0
        
        # HSV范围
        self.wall_hsv_range = None
        self.player_hsv_range = None
        
        # 智能推荐
        self.recommend_sat_filter_off = False
        
        # 设置UI
        self.setup_ui()
        
        # 初始显示
        self.update_display_with_markers()
    
    def setup_ui(self):
        """设置界面"""
        layout = QVBoxLayout(self)
        
        # ===== 说明 =====
        help_label = QLabel(
            "INFO: 使用说明：\n"
            "1. 点击「选择墙体」，在左侧图像上点击墙体区域（建议5-10个点，覆盖不同亮度）\n"
            "2. 点击「选择人物」，在左侧图像上点击人物标记（1-2个点）\n"
            "3. 点击「计算HSV范围」，系统自动计算颜色范围\n"
            "4. 查看右侧二值化预览效果，满意后点击「确定」"
        )
        help_label.setWordWrap(True)
        help_label.setStyleSheet("background-color: #2c3e50; color: white; padding: 10px; border-radius: 5px;")
        layout.addWidget(help_label)
        
        # ===== 按钮组 =====
        btn_layout = QHBoxLayout()
        
        self.wall_mode_btn = QPushButton("[BLUE] 选择墙体")
        self.wall_mode_btn.setStyleSheet("padding: 10px; font-size: 14px;")
        self.wall_mode_btn.clicked.connect(lambda: self.set_mode('wall'))
        btn_layout.addWidget(self.wall_mode_btn)
        
        self.player_mode_btn = QPushButton("[GREEN] 选择人物")
        self.player_mode_btn.setStyleSheet("padding: 10px; font-size: 14px;")
        self.player_mode_btn.clicked.connect(lambda: self.set_mode('player'))
        btn_layout.addWidget(self.player_mode_btn)
        
        self.calc_btn = QPushButton("[ZOOM] 计算HSV范围")
        self.calc_btn.setStyleSheet("padding: 10px; font-size: 14px; background-color: #e74c3c; color: white;")
        self.calc_btn.clicked.connect(self.calculate_hsv_ranges)
        btn_layout.addWidget(self.calc_btn)
        
        self.reset_btn = QPushButton("[REFRESH] 重置")
        self.reset_btn.setStyleSheet("padding: 10px; font-size: 14px;")
        self.reset_btn.clicked.connect(self.reset_selection)
        btn_layout.addWidget(self.reset_btn)
        
        layout.addLayout(btn_layout)
        
        # ===== 主显示区 =====
        main_layout = QHBoxLayout()
        
        # 左侧：原图+标记
        left_group = QGroupBox("原图（点击选择颜色）")
        left_layout = QVBoxLayout()
        
        zoom_layout = QHBoxLayout()
        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setRange(50, 400)
        self.zoom_slider.setValue(100)
        self.zoom_slider.valueChanged.connect(self.on_zoom_changed)
        zoom_layout.addWidget(QLabel("缩放"))
        zoom_layout.addWidget(self.zoom_slider)
        self.zoom_value_label = QLabel("100%")
        zoom_layout.addWidget(self.zoom_value_label)
        left_layout.addLayout(zoom_layout)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.image_label = ClickableImageLabel(self.original_width, self.original_height)
        self.image_label.setStyleSheet("background-color: black; border: 2px solid #3498db;")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.pixel_clicked.connect(self.on_pixel_clicked)
        self.image_label.wheel_zoom.connect(self.on_wheel_zoom)
        self.scroll_area.setWidget(self.image_label)
        left_layout.addWidget(self.scroll_area)
        
        left_group.setLayout(left_layout)
        main_layout.addWidget(left_group, 1)
        
        # 右侧：预览效果
        right_group = QGroupBox("二值化预览")
        right_layout = QVBoxLayout()
        
        self.preview_label = QLabel()
        self.preview_label.setMinimumSize(400, 400)
        self.preview_label.setStyleSheet("background-color: black; border: 2px solid #2ecc71;")
        self.preview_label.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(self.preview_label)
        
        right_group.setLayout(right_layout)
        main_layout.addWidget(right_group, 1)
        
        layout.addLayout(main_layout)
        
        # ===== 结果显示 =====
        result_group = QGroupBox("计算结果")
        result_layout = QVBoxLayout()
        
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setMaximumHeight(120)
        self.result_text.setStyleSheet("font-family: Consolas, monospace; font-size: 12px;")
        result_layout.addWidget(self.result_text)
        
        result_group.setLayout(result_layout)
        layout.addWidget(result_group)
        
        # ===== 确定/取消按钮 =====
        footer_layout = QHBoxLayout()
        
        self.ok_btn = QPushButton("[OK] 确定")
        self.ok_btn.setStyleSheet("padding: 10px; font-size: 14px; background-color: #27ae60; color: white;")
        self.ok_btn.clicked.connect(self.accept)
        self.ok_btn.setEnabled(False)
        footer_layout.addWidget(self.ok_btn)
        
        self.cancel_btn = QPushButton("[CANCEL] 取消")
        self.cancel_btn.setStyleSheet("padding: 10px; font-size: 14px;")
        self.cancel_btn.clicked.connect(self.reject)
        footer_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(footer_layout)
        
        # 初始模式
        self.set_mode('wall')
    
    def set_mode(self, mode):
        """设置当前模式"""
        self.current_mode = mode
        
        if mode == 'wall':
            self.wall_mode_btn.setStyleSheet("padding: 10px; font-size: 14px; background-color: #3498db; color: white;")
            self.player_mode_btn.setStyleSheet("padding: 10px; font-size: 14px;")
            self.result_text.append(f"\n📍 模式：选择墙体（已选 {len(self.wall_points)} 个点）")
        else:
            self.wall_mode_btn.setStyleSheet("padding: 10px; font-size: 14px;")
            self.player_mode_btn.setStyleSheet("padding: 10px; font-size: 14px; background-color: #2ecc71; color: white;")
            self.result_text.append(f"\n📍 模式：选择人物（已选 {len(self.player_points)} 个点）")
    
    def on_pixel_clicked(self, x, y):
        """
        像素点击事件（坐标已经是原始图像坐标）
        
        Args:
            x, y: 原始图像坐标
        """
        # 边界检查
        if x < 0 or x >= self.original_width or y < 0 or y >= self.original_height:
            self.result_text.append(f"⚠️ 点击超出范围: ({x}, {y})")
            return
        
        # 获取像素值
        bgr = self.processed_screenshot[y, x]
        hsv = cv2.cvtColor(self.processed_screenshot, cv2.COLOR_BGR2HSV)[y, x]
        
        # 记录点击点
        if self.current_mode == 'wall':
            self.wall_points.append((x, y))
            self.result_text.append(f"  ✓ 墙体 #{len(self.wall_points)}: ({x},{y}) BGR{tuple(bgr)} HSV{tuple(hsv)}")
        else:
            self.player_points.append((x, y))
            self.result_text.append(f"  ✓ 人物 #{len(self.player_points)}: ({x},{y}) BGR{tuple(bgr)} HSV{tuple(hsv)}")
        
        # 更新显示
        self.update_display_with_markers()
    
    def update_display_with_markers(self):
        """更新显示（带标记）"""
        # 显示原图；标记由QPainter在缩放后的pixmap上绘制，保持屏幕固定大小
        self._show_image(self.image_label, self.processed_screenshot)
        if self.wall_hsv_range is None:
            self._show_image(self.preview_label, self.processed_screenshot)
    
    def calculate_hsv_ranges(self):
        """计算HSV范围"""
        if len(self.wall_points) == 0 and len(self.player_points) == 0:
            self.result_text.append("\n⚠️ 请先选择至少一个点！")
            return
        
        self.result_text.append("\n" + "="*50)
        self.result_text.append("[ZOOM] 开始计算HSV范围...")
        
        # 转HSV (使用预处理后的图像)
        hsv = cv2.cvtColor(self.processed_screenshot, cv2.COLOR_BGR2HSV)
        
        # 计算墙体HSV范围
        if len(self.wall_points) > 0:
            wall_hsv_values = [hsv[y, x] for x, y in self.wall_points]
            self.wall_hsv_range = self._calculate_range(wall_hsv_values, "墙体")
            
            # 智能检测：如果墙体饱和度较高，建议关闭饱和度过滤
            mean_s = np.mean([v[1] for v in wall_hsv_values])
            if mean_s > 30:
                self.recommend_sat_filter_off = True
                self.result_text.append("\n⚠️ 检测到墙体饱和度较高（彩色墙体）")
                self.result_text.append("💡 建议：在高级设置中【关闭饱和度过滤】或【设置过滤半径】")
                self.result_text.append("   (点击确定后将自动为您调整)")
            else:
                self.recommend_sat_filter_off = False
        
        # 计算人物HSV范围
        if len(self.player_points) > 0:
            player_hsv_values = [hsv[y, x] for x, y in self.player_points]
            self.player_hsv_range = self._calculate_range(player_hsv_values, "人物")
        
        # 更新预览
        self.update_preview()
        
        # 启用确定按钮
        self.ok_btn.setEnabled(True)
        
        self.result_text.append("\n[DONE] 计算完成！查看右侧预览效果")
    
    def _calculate_range(self, hsv_values, label):
        """
        计算HSV范围（带容差）
        
        Args:
            hsv_values: HSV值列表
            label: 标签名称
        
        Returns:
            (min_hsv, max_hsv)
        """
        hsv_array = np.array(hsv_values)
        
        # 计算均值和标准差
        mean_hsv = np.mean(hsv_array, axis=0)
        std_hsv = np.std(hsv_array, axis=0)
        
        # 设置容差（2倍标准差，至少保留一定范围）
        tolerance = np.maximum(std_hsv * 2, [5, 20, 20])
        
        # 计算范围
        min_hsv = np.maximum(mean_hsv - tolerance, [0, 0, 0])
        max_hsv = np.minimum(mean_hsv + tolerance, [179, 255, 255])
        
        # 显示结果
        self.result_text.append(f"\n📊 {label}颜色（采样{len(hsv_values)}点）：")
        self.result_text.append(f"  均值: {mean_hsv.astype(int)}")
        self.result_text.append(f"  范围: {min_hsv.astype(int)} ~ {max_hsv.astype(int)}")
        
        return (min_hsv.astype(int), max_hsv.astype(int))
    
    def update_preview(self):
        """更新预览"""
        if self.wall_hsv_range is None:
            return

        # 记录HSV范围
        min_hsv, max_hsv = self.wall_hsv_range
      
        # 转换为HSV
        hsv = cv2.cvtColor(self.processed_screenshot, cv2.COLOR_BGR2HSV)


        # 记录选择的像素点信息
        if self.wall_points:
          
            for i, (x, y) in enumerate(self.wall_points):
                if 0 <= x < hsv.shape[1] and 0 <= y < hsv.shape[0]:
                    pixel_hsv = hsv[y, x]
                    in_range = (pixel_hsv >= min_hsv).all() and (pixel_hsv <= max_hsv).all()
                

        # 墙体mask
        wall_mask = cv2.inRange(
            hsv,
            self.wall_hsv_range[0],
            self.wall_hsv_range[1]
        )

        # 记录mask统计信息
        white_pixels = np.count_nonzero(wall_mask)
        total_pixels = wall_mask.size
        white_ratio = white_pixels / total_pixels if total_pixels > 0 else 0


        # 形态学处理
        kernel = np.ones((3, 3), np.uint8)
        wall_mask_before_morph = wall_mask.copy()  # 保存形态学处理前的状态
        wall_mask_after_close = wall_mask.copy()  # 保存close操作前的状态
        wall_mask = cv2.morphologyEx(wall_mask, cv2.MORPH_CLOSE, kernel)
        pixels_after_close = np.count_nonzero(wall_mask)
        pixels_after_close_diff = np.count_nonzero(wall_mask_after_close) - pixels_after_close
 

        # 显示
        self._show_image(self.preview_label, wall_mask)

        # 保存预览结果
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        preview_filename = f"preview_result_{timestamp}.png"
        cv2.imwrite(preview_filename, wall_mask)


        # 保存处理前的mask用于对比
        before_morph_filename = f"preview_before_morph_{timestamp}.png"
        cv2.imwrite(before_morph_filename, wall_mask_before_morph)


        # 保存HSV范围信息到日志文件
        log_filename = f"preview_log_{timestamp}.txt"
        with open(log_filename, 'w', encoding='utf-8') as f:
            f.write(f"二值化预览日志 - {datetime.now()}\n")
            f.write(f"HSV范围: [{min_hsv[0]}, {min_hsv[1]}, {min_hsv[2]}] ~ [{max_hsv[0]}, {max_hsv[1]}, {max_hsv[2]}]\n")
            f.write(f"图像尺寸: {self.processed_screenshot.shape}\n")
            f.write(f"选择的墙体点: {len(self.wall_points)} 个\n")
            for i, (x, y) in enumerate(self.wall_points):
                if 0 <= x < hsv.shape[1] and 0 <= y < hsv.shape[0]:
                    pixel_hsv = hsv[y, x]
                    in_range = (pixel_hsv >= min_hsv).all() and (pixel_hsv <= max_hsv).all()
                    f.write(f"点{i+1} ({x},{y}): HSV{pixel_hsv} {'在范围内' if in_range else '超出范围'}\n")
            f.write(f"处理前mask白色像素: {white_pixels}/{total_pixels} ({white_ratio*100:.2f}%)\n")
            f.write(f"Close操作后白色像素: {pixels_after_close}/{total_pixels}\n")
            f.write(f"形态学处理变化像素: {pixels_after_close_diff}\n")
            f.write(f"[DONE] 形态学处理完成，保留了识别的墙体特征\n")

    
    def reset_selection(self):
        """重置选择"""
        self.wall_points = []
        self.player_points = []
        self.wall_hsv_range = None
        self.player_hsv_range = None
        
        self.result_text.clear()
        self.result_text.append("[REFRESH] 已重置，请重新选择")
        
        self.ok_btn.setEnabled(False)
        
        # 重新显示原图
        self._show_image(self.image_label, self.processed_screenshot)
        self.preview_label.clear()
    
    def _show_image(self, label, img):
        """在QLabel上显示OpenCV图像"""
        if img is not None:
            if len(img.shape) == 2:
                h, w = img.shape
                q_img = QImage(img.data, w, h, w, QImage.Format_Grayscale8)
            else:
                rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb.shape
                bytes_per_line = ch * w
                q_img = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(q_img)
        else:
            rgb = cv2.cvtColor(self.screenshot, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            bytes_per_line = ch * w
            q_img = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(q_img)
        
        if isinstance(label, ClickableImageLabel):
            target_w = int(self.original_width * self.zoom)
            target_h = int(self.original_height * self.zoom)
            scaled_pixmap = pixmap.scaled(target_w, target_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            # 在缩放后的pixmap上绘制标记（固定屏幕大小）
            painter = QPainter(scaled_pixmap)
            pen_wall = QPen(QColor(52, 152, 219), 2)   # 蓝色
            pen_player = QPen(QColor(46, 204, 113), 2) # 绿色
            radius_outer = 5
            radius_inner = 2
            # 计算坐标缩放
            disp_w = scaled_pixmap.width()
            disp_h = scaled_pixmap.height()
            scale_x = disp_w / self.original_width
            scale_y = disp_h / self.original_height
            # 绘制墙体标记
            painter.setPen(pen_wall)
            for x, y in self.wall_points:
                dx = int(x * scale_x)
                dy = int(y * scale_y)
                painter.drawEllipse(dx - radius_outer, dy - radius_outer, radius_outer*2, radius_outer*2)
                painter.setBrush(QColor(52, 152, 219))
                painter.drawEllipse(dx - radius_inner, dy - radius_inner, radius_inner*2, radius_inner*2)
                painter.setBrush(Qt.NoBrush)
            # 绘制人物标记
            painter.setPen(pen_player)
            for x, y in self.player_points:
                dx = int(x * scale_x)
                dy = int(y * scale_y)
                painter.drawEllipse(dx - radius_outer, dy - radius_outer, radius_outer*2, radius_outer*2)
                painter.setBrush(QColor(46, 204, 113))
                painter.drawEllipse(dx - radius_inner, dy - radius_inner, radius_inner*2, radius_inner*2)
                painter.setBrush(Qt.NoBrush)
            painter.end()
            label.setPixmap(scaled_pixmap)
            label.setFixedSize(scaled_pixmap.size())
            label.set_displayed_size(scaled_pixmap.width(), scaled_pixmap.height())
        else:
            label_size = label.size()
            scaled_pixmap = pixmap.scaled(label_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            label.setPixmap(scaled_pixmap)
    
    def get_result(self):
        """获取结果"""
        return {
            'wall_hsv': self.wall_hsv_range,
            'player_hsv': self.player_hsv_range,
            'recommend_sat_filter_off': self.recommend_sat_filter_off
        }
    
    def on_zoom_changed(self, value):
        self.zoom = max(0.1, value / 100.0)
        self.zoom_value_label.setText(f"{int(self.zoom*100)}%")
        self.update_display_with_markers()
    
    def on_wheel_zoom(self, delta):
        step = 10 if delta > 0 else -10
        new_val = max(self.zoom_slider.minimum(), min(self.zoom_slider.maximum(), self.zoom_slider.value() + step))
        if new_val != self.zoom_slider.value():
            self.zoom_slider.setValue(new_val)
