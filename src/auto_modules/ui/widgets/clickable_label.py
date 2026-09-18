
from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QMouseEvent

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
            return

        click_x = event.pos().x()
        click_y = event.pos().y()

        label_width = self.width()
        label_height = self.height()

        x_offset = (label_width - self.displayed_width) // 2
        y_offset = (label_height - self.displayed_height) // 2

        pixmap_x = click_x - x_offset
        pixmap_y = click_y - y_offset

        if pixmap_x < 0 or pixmap_x >= self.displayed_width or pixmap_y < 0 or pixmap_y >= self.displayed_height:
            return

        scale_x = self.original_width / self.displayed_width
        scale_y = self.original_height / self.displayed_height

        original_x = int(pixmap_x * scale_x)
        original_y = int(pixmap_y * scale_y)

        original_x = max(0, min(original_x, self.original_width - 1))
        original_y = max(0, min(original_y, self.original_height - 1))

        self.pixel_clicked.emit(original_x, original_y)

    def wheelEvent(self, event):
        self.wheel_zoom.emit(event.angleDelta().y())
