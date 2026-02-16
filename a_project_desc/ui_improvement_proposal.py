"""
UI改进方案实现代码

针对以下两个问题的解决方案：
1. 全局拼接地图默认是缩小的全局视图状态，缩放不够丝滑
2. 当前捕获窗口应放在右侧边栏，用更小的窗口表示，让全局拼接地图占据更多画幅
"""

# 首先，我们需要修改 ScalableMapWidget 类以改善缩放体验
class ImprovedScalableMapWidget(QWidget):
    """
    改进的可缩放地图组件
    1. 默认显示适合窗口的缩放级别
    2. 更平滑的缩放体验
    3. 自动适应功能
    """

    pixel_clicked = Signal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)

        # 地图数据
        self.original_pixmap = None
        self.current_pixmap = None
        self.scale_factor = 1.0
        self.min_scale = 0.01  # 更小的最小缩放
        self.max_scale = 10.0
        self.auto_fit_enabled = True  # 启用自动适应

        # 拖拽相关
        self.is_dragging = False
        self.last_mouse_pos = None

        # 创建滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # 创建图像标签
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.scroll_area.setWidget(self.image_label)

        # 布局
        layout = QVBoxLayout(self)
        layout.addWidget(self.scroll_area)

        # 连接事件
        self.image_label.mousePressEvent = self._mouse_press_event
        self.image_label.mouseMoveEvent = self._mouse_move_event
        self.image_label.mouseReleaseEvent = self._mouse_release_event
        self.image_label.wheelEvent = self._wheel_event

    def set_image(self, pixmap):
        """设置要显示的图像，并自动调整到适合窗口的大小"""
        self.original_pixmap = pixmap
        self.current_pixmap = pixmap
        
        if pixmap:
            self.image_label.setPixmap(pixmap)
            self.image_label.adjustSize()
            
            # 自动适应窗口大小
            if self.auto_fit_enabled:
                self.fit_to_view()
        else:
            self.image_label.clear()

    def fit_to_view(self):
        """自动适应视图大小"""
        if not self.original_pixmap:
            return
            
        # 获取滚动区域的视口大小
        viewport_size = self.scroll_area.viewport().size()
        
        # 计算合适的缩放比例
        pixmap_width = self.original_pixmap.width()
        pixmap_height = self.original_pixmap.height()
        
        width_ratio = viewport_size.width() / pixmap_width
        height_ratio = viewport_size.height() / pixmap_height
        
        # 选择较小的比例以确保整个图像都能显示
        fit_scale = min(width_ratio, height_ratio) * 0.9  # 留一些边距
        
        # 限制在允许的缩放范围内
        self.scale_factor = max(self.min_scale, min(fit_scale, self.max_scale))
        
        self._apply_scale()

    def zoom_in(self):
        """平滑放大 - 使用更小的步进"""
        new_scale = self.scale_factor * 1.1  # 从1.2改为1.1，更平滑
        if new_scale <= self.max_scale:
            self.scale_factor = new_scale
            self._apply_scale()

    def zoom_out(self):
        """平滑缩小 - 使用更小的步进"""
        new_scale = self.scale_factor / 1.1  # 从1.2改为1.1，更平滑
        if new_scale >= self.min_scale:
            self.scale_factor = new_scale
            self._apply_scale()

    def smooth_zoom_to(self, target_scale):
        """平滑缩放到目标比例（可用于动画效果）"""
        self.scale_factor = max(self.min_scale, min(target_scale, self.max_scale))
        self._apply_scale()

    def reset_zoom(self):
        """重置缩放，可以选择回到适应视图状态"""
        self.scale_factor = 1.0
        if self.auto_fit_enabled:
            self.fit_to_view()
        else:
            self._apply_scale()

    def set_scale(self, scale):
        """设置特定缩放级别"""
        self.scale_factor = max(self.min_scale, min(scale, self.max_scale))
        self._apply_scale()

    def _apply_scale(self):
        """应用缩放"""
        if self.original_pixmap:
            new_width = int(self.original_pixmap.width() * self.scale_factor)
            new_height = int(self.original_pixmap.height() * self.scale_factor)

            scaled_pixmap = self.original_pixmap.scaled(
                new_width, new_height,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation  # 使用高质量变换
            )

            self.current_pixmap = scaled_pixmap
            self.image_label.setPixmap(scaled_pixmap)
            self.image_label.adjustSize()

    def _mouse_press_event(self, event):
        """鼠标按下事件"""
        if event.button() == Qt.LeftButton:
            self.is_dragging = True
            self.last_mouse_pos = event.globalPosition().toPoint()
        elif event.button() == Qt.RightButton:
            # 右键重置缩放
            self.reset_zoom()

    def _mouse_move_event(self, event):
        """鼠标移动事件"""
        if self.is_dragging and self.last_mouse_pos:
            # 拖拽滚动
            delta = event.globalPosition().toPoint() - self.last_mouse_pos
            self.scroll_area.horizontalScrollBar().setValue(
                self.scroll_area.horizontalScrollBar().value() - delta.x()
            )
            self.scroll_area.verticalScrollBar().setValue(
                self.scroll_area.verticalScrollBar().value() - delta.y()
            )
            self.last_mouse_pos = event.globalPosition().toPoint()

    def _mouse_release_event(self, event):
        """鼠标释放事件"""
        self.is_dragging = False
        self.last_mouse_pos = None

    def _wheel_event(self, event: QWheelEvent):
        """滚轮事件 - 实现更精细的缩放"""
        if event.modifiers() & Qt.ControlModifier:
            # Ctrl+滚轮进行缩放，使用更小的增量
            delta = event.angleDelta().y()
            # 根据滚轮滚动的距离调整缩放步进
            zoom_factor = 1 + abs(delta) / 1200  # 更精细的控制
            
            if delta > 0:
                self.scale_factor *= zoom_factor
            else:
                self.scale_factor /= zoom_factor
                
            # 限制缩放范围
            self.scale_factor = max(self.min_scale, min(self.scale_factor, self.max_scale))
            self._apply_scale()
        else:
            # 普通滚轮滚动
            self.scroll_area.wheelEvent(event)


# 修改主窗口的布局以实现新的UI结构
def create_improved_display_panel(self):
    """创建改进的显示面板 - 当前捕获放在右侧边栏"""
    panel = QWidget()
    
    # 使用水平布局，左侧主地图，右侧边栏
    main_layout = QHBoxLayout(panel)

    # 左侧：全局地图（主要区域）
    left_panel = QWidget()
    left_layout = QVBoxLayout(left_panel)

    # 全局地图
    self.global_group = CollapsibleMapGroup("全局拼接地图 (点击设置导航点)")
    self.global_group.setMinimumSize(800, 600)  # 增加默认大小

    # 使用改进的地图组件
    self.global_map_widget = ImprovedScalableMapWidget()  # 使用改进的组件
    self.global_map_widget.setStyleSheet("background-color: black;")
    self.global_map_widget.pixel_clicked.connect(self.on_map_click)

    # 将改进的地图组件放入组中
    self.global_group.scalable_map.setParent(None)  # 移除旧组件
    self.global_group.main_layout.insertWidget(1, self.global_map_widget)  # 插入新组件

    left_layout.addWidget(self.global_group)
    main_layout.addWidget(left_panel, 3)  # 主区域占3份

    # 右侧：边栏（当前捕获和其他信息）
    sidebar_panel = QWidget()
    sidebar_layout = QVBoxLayout(sidebar_panel)
    sidebar_layout.setSpacing(10)

    # 当前捕获（更小的窗口）
    current_group = QGroupBox("当前捕获（叠加识别结果）")
    current_layout = QVBoxLayout()

    self.current_label = QLabel()
    self.current_label.setMinimumSize(250, 180)  # 显著减小尺寸
    self.current_label.setMaximumSize(250, 180)  # 限制最大尺寸
    self.current_label.setStyleSheet("background-color: black;")
    self.current_label.setAlignment(Qt.AlignCenter)
    current_layout.addWidget(self.current_label)

    current_group.setLayout(current_layout)
    sidebar_layout.addWidget(current_group)

    # 统计信息也放在边栏
    stats_group = QGroupBox("统计信息")
    stats_layout = QVBoxLayout()

    self.stats_text = QTextEdit()
    self.stats_text.setReadOnly(True)
    self.stats_text.setMinimumHeight(150)
    stats_layout.addWidget(self.stats_text)

    stats_group.setLayout(stats_layout)
    sidebar_layout.addWidget(stats_group)

    # 添加弹性空间，使组件靠上排列
    sidebar_layout.addStretch()
    
    main_layout.addWidget(sidebar_panel, 1)  # 边栏占1份

    return panel


# 以下是完整的修改方案，需要在MainWindow类中做如下更改：

"""
在MainWindow.__init__()中：
1. 替换原来的create_display_panel调用为create_improved_display_panel
2. 确保引入所需的Qt模块
"""

# 需要添加到文件顶部的导入
"""
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QGroupBox, QCheckBox,
    QSpinBox, QTextEdit, QApplication, QScrollArea, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap, QWheelEvent
"""

# 在MainWindow类中还需要修改update_displays方法以适应新的布局
def improved_update_displays(self, current_img, combined_mask):
    """更新显示 - 适配新的布局"""
    # ===== 当前捕获 =====
    display_img = current_img.copy()

    # 叠加识别结果（绿色半透明）
    mask_colored = cv2.cvtColor(combined_mask, cv2.COLOR_GRAY2BGR)
    mask_colored[:, :, 0] = 0  # 去掉蓝色通道
    display_img = cv2.addWeighted(display_img, 0.7, mask_colored, 0.3, 0)

    # 缩放到边栏大小
    h, w = display_img.shape[:2]
    target_w, target_h = 240, 170  # 略小于设定的最大尺寸，留边距
    scale = min(target_w / w, target_h / h)
    new_w, new_h = int(w * scale), int(h * scale)
    display_img = cv2.resize(display_img, (new_w, new_h))

    # 转换为QPixmap
    self._show_image(self.current_label, display_img)

    # ===== 全局地图（显示完整探索地图 + 视野框）=====
    # 获取当前位置
    current_x, current_y = self.stitcher.get_current_position()

    # 获取增强后的地图（墙体强化+背景弱化）
    global_map = self.stitcher.get_enhanced_map(margin=500)

    if global_map.size > 0:
        # 转彩色
        global_colored = cv2.cvtColor(global_map, cv2.COLOR_GRAY2BGR)

        # 计算视野框在裁剪地图上的位置
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

            # 设置到改进的可缩放地图组件
            self.global_map_widget.set_image(pixmap)

"""
实施这些更改将会：

1. 改善全局地图的默认显示状态，使其自动适应窗口大小
2. 提供更平滑的缩放体验，使用更小的缩放步进
3. 重新安排UI布局，将当前捕获窗口移到右侧边栏，使用更小的固定尺寸
4. 让全局拼接地图占据更多的界面空间，提升用户体验
"""