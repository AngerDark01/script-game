
from PySide6.QtWidgets import (
    QLabel, QScrollArea, QVBoxLayout, QWidget, QGroupBox, QPushButton,
    QHBoxLayout, QSizePolicy
)
from PySide6.QtCore import Signal, Qt, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QMouseEvent, QPixmap, QWheelEvent

class ClickableImageLabel(QLabel):
    """
    可点击的图像标签
    正确处理坐标转换：显示坐标 → 原始图像坐标
    """

    pixel_clicked = Signal(int, int)
    wheel_zoom = Signal(int)

    def __init__(self, original_width=0, original_height=0, parent=None):
        super().__init__(parent)
        self.original_width = original_width
        self.original_height = original_height
        self.displayed_width = 0
        self.displayed_height = 0

    def set_original_size(self, width, height):
        """更新原始图像尺寸"""
        self.original_width = width
        self.original_height = height

    def set_displayed_size(self, width, height):
        """设置显示的pixmap尺寸"""
        self.displayed_width = width
        self.displayed_height = height

    def mousePressEvent(self, event: QMouseEvent):
        """鼠标点击事件"""
        if event.button() != Qt.LeftButton:
            return

        if self.displayed_width == 0 or self.displayed_height == 0:
            # print("⚠️ 显示尺寸未设置")
            return

        # === 步骤1：获取点击位置（相对于QLabel） ===
        click_x = event.pos().x()
        click_y = event.pos().y()

        # === 步骤2：计算pixmap在label中的偏移（居中显示） ===
        label_width = self.width()
        label_height = self.height()

        x_offset = (label_width - self.displayed_width) // 2
        y_offset = (label_height - self.displayed_height) // 2

        # === 步骤3：转换为pixmap坐标 ===
        pixmap_x = click_x - x_offset
        pixmap_y = click_y - y_offset

        # === 步骤4：检查是否在pixmap范围内 ===
        if pixmap_x < 0 or pixmap_x >= self.displayed_width or pixmap_y < 0 or pixmap_y >= self.displayed_height:
            # print(f"⚠️ 点击在图像外: Label({click_x},{click_y}) → Pixmap({pixmap_x},{pixmap_y})")
            return

        # === 步骤5：计算缩放比例并转换为原始图像坐标 ===
        # 防止除零错误
        if self.displayed_width == 0 or self.displayed_height == 0:
            return

        scale_x = self.original_width / self.displayed_width
        scale_y = self.original_height / self.displayed_height

        original_x = int(pixmap_x * scale_x)
        original_y = int(pixmap_y * scale_y)

        # === 步骤6：边界检查 ===
        original_x = max(0, min(original_x, self.original_width - 1))
        original_y = max(0, min(original_y, self.original_height - 1))

        # print(f"🖱️ 坐标转换: Label({click_x},{click_y}) → Pixmap({pixmap_x},{pixmap_y}) → Original({original_x},{original_y}) | 缩放:{scale_x:.2f}x{scale_y:.2f}")

        # === 步骤7：发送信号 ===
        self.pixel_clicked.emit(original_x, original_y)

    def wheelEvent(self, event):
        self.wheel_zoom.emit(event.angleDelta().y())


class ScalableMapWidget(QWidget):
    """
    可缩放的地图组件
    支持滚轮缩放、拖拽和平滑缩放
    """

    pixel_clicked = Signal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)

        # 地图数据
        self.original_pixmap = None
        self.current_pixmap = None
        self.scale_factor = 1.0
        self.min_scale = 0.1
        self.max_scale = 10.0

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
        """设置要显示的图像"""
        self.original_pixmap = pixmap
        self.current_pixmap = pixmap
        if pixmap:
            self.image_label.setPixmap(pixmap)
            self.image_label.adjustSize()
        else:
            self.image_label.clear()

    def zoom_in(self):
        """放大"""
        new_scale = self.scale_factor * 1.2
        if new_scale <= self.max_scale:
            self.scale_factor = new_scale
            self._apply_scale()

    def zoom_out(self):
        """缩小"""
        new_scale = self.scale_factor / 1.2
        if new_scale >= self.min_scale:
            self.scale_factor = new_scale
            self._apply_scale()

    def reset_zoom(self):
        """重置缩放"""
        self.scale_factor = 1.0
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
                Qt.SmoothTransformation
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
        """滚轮事件 - 实现缩放"""
        if event.modifiers() & Qt.ControlModifier:
            # Ctrl+滚轮进行缩放
            if event.angleDelta().y() > 0:
                self.zoom_in()
            else:
                self.zoom_out()
        else:
            # 普通滚轮滚动
            self.scroll_area.wheelEvent(event)


class CollapsibleMapGroup(QGroupBox):
    """
    可收缩的地图组组件
    """

    def __init__(self, title="全局拼接地图 (点击设置导航点)", parent=None):
        super().__init__(title, parent)

        self.collapsed = False
        self.original_height = None

        # 设置可勾选以实现收缩功能
        self.setCheckable(True)
        self.setChecked(True)  # 默认展开

        # 创建主布局
        self.main_layout = QVBoxLayout(self)

        # 创建可缩放地图组件
        self.scalable_map = ScalableMapWidget()

        # 创建控制按钮布局
        self.controls_layout = QHBoxLayout()

        # 添加缩放控制按钮
        self.zoom_in_btn = QPushButton("🔍+")
        self.zoom_in_btn.clicked.connect(self.scalable_map.zoom_in)
        self.zoom_in_btn.setToolTip("放大 (Ctrl+滚轮向上)")

        self.zoom_out_btn = QPushButton("🔍-")
        self.zoom_out_btn.clicked.connect(self.scalable_map.zoom_out)
        self.zoom_out_btn.setToolTip("缩小 (Ctrl+滚轮向下)")

        self.reset_zoom_btn = QPushButton("🔄")
        self.reset_zoom_btn.clicked.connect(self.scalable_map.reset_zoom)
        self.reset_zoom_btn.setToolTip("重置缩放")

        # 将按钮添加到控制布局
        self.controls_layout.addWidget(self.zoom_in_btn)
        self.controls_layout.addWidget(self.zoom_out_btn)
        self.controls_layout.addWidget(self.reset_zoom_btn)
        self.controls_layout.addStretch()  # 添加弹性空间

        # 将控制按钮和地图添加到主布局
        self.main_layout.addLayout(self.controls_layout)
        self.main_layout.addWidget(self.scalable_map)

        # 连接收缩/展开信号
        self.toggled.connect(self._on_toggled)

    def set_map_image(self, pixmap):
        """设置地图图像"""
        self.scalable_map.set_image(pixmap)

    def _on_toggled(self, checked):
        """处理收缩/展开事件 - 修复了原版本中的错误"""
        if checked:
            # 展开
            self.scalable_map.setVisible(True)
            # 修复：直接显示控制按钮布局
            self.controls_layout.parentWidget().setVisible(True)
        else:
            # 收缩
            self.scalable_map.setVisible(False)
            # 隐藏控制按钮布局
            self.controls_layout.parentWidget().setVisible(False)

    def mousePressEvent(self, event):
        """允许通过点击标题栏来收缩/展开"""
        super().mousePressEvent(event)
