"""
交互式颜色选择工具 v2.1
核心修复：100%准确的坐标映射（显示坐标 → 原始图像坐标）
"""

import cv2
from PySide6.QtWidgets import QDialog
from PySide6.QtCore import Qt

from core.vision import HSVRecognizer
from ..widgets.clickable_label import ClickableImageLabel
from .color_picker.hsv_ranges import (
    bgr_to_hsv,
    calculate_hsv_range,
    hsv_values_at_points,
    mean_saturation,
)
from .color_picker.image_renderer import draw_sample_markers, pixmap_from_image
from .color_picker.debug_output import is_wall_preview_debug_enabled, write_wall_preview_debug
from .color_picker.layout import build_color_picker_ui
from .color_picker.preview import build_wall_preview


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
        build_color_picker_ui(self)
    
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
        hsv = bgr_to_hsv(self.processed_screenshot)
        
        # 计算墙体HSV范围
        if len(self.wall_points) > 0:
            wall_hsv_values = hsv_values_at_points(hsv, self.wall_points)
            self.wall_hsv_range = self._calculate_range(wall_hsv_values, "墙体")
            
            # 智能检测：如果墙体饱和度较高，建议关闭饱和度过滤
            mean_s = mean_saturation(wall_hsv_values)
            if mean_s > 30:
                self.recommend_sat_filter_off = True
                self.result_text.append("\n⚠️ 检测到墙体饱和度较高（彩色墙体）")
                self.result_text.append("💡 建议：在高级设置中【关闭饱和度过滤】或【设置过滤半径】")
                self.result_text.append("   (点击确定后将自动为您调整)")
            else:
                self.recommend_sat_filter_off = False
        
        # 计算人物HSV范围
        if len(self.player_points) > 0:
            player_hsv_values = hsv_values_at_points(hsv, self.player_points)
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
        mean_hsv, min_hsv, max_hsv = calculate_hsv_range(hsv_values)
        
        # 显示结果
        self.result_text.append(f"\n📊 {label}颜色（采样{len(hsv_values)}点）：")
        self.result_text.append(f"  均值: {mean_hsv.astype(int)}")
        self.result_text.append(f"  范围: {min_hsv.astype(int)} ~ {max_hsv.astype(int)}")
        
        return (min_hsv, max_hsv)
    
    def update_preview(self):
        """更新预览"""
        preview = build_wall_preview(self.processed_screenshot, self.wall_hsv_range)
        if preview is None:
            return
        self._show_image(self.preview_label, preview.mask)
        if is_wall_preview_debug_enabled():
            write_wall_preview_debug(
                output_dir="debug/color_picker",
                wall_mask=preview.mask,
                wall_mask_before_morph=preview.mask_before_morph,
                hsv=preview.hsv,
                min_hsv=preview.min_hsv,
                max_hsv=preview.max_hsv,
                image_shape=self.processed_screenshot.shape,
                wall_points=self.wall_points,
                white_pixels=preview.white_pixels,
                total_pixels=preview.total_pixels,
                white_ratio=preview.white_ratio,
                pixels_after_close=preview.pixels_after_close,
                pixels_after_close_diff=preview.pixels_after_close_diff,
            )
    
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
        pixmap = pixmap_from_image(img, fallback_image=self.screenshot)
        
        if isinstance(label, ClickableImageLabel):
            scaled_pixmap = draw_sample_markers(
                pixmap,
                original_width=self.original_width,
                original_height=self.original_height,
                zoom=self.zoom,
                wall_points=self.wall_points,
                player_points=self.player_points,
            )
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
