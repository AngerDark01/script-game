from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPen, QColor, QPainterPath

class OverlayWindow(QWidget):
    """
    屏幕覆盖层 (Transparent Overlay)
    用于在游戏画面上绘制可视化的映射范围框
    """
    def __init__(self):
        super().__init__()

        # 无边框、透明背景、置顶、鼠标穿透
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool |  # 不在任务栏显示
            Qt.WindowTransparentForInput # 鼠标穿透 (关键！)
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground, False)

        # 全屏覆盖
        screen_geometry = QApplication.primaryScreen().geometry()
        self.setGeometry(screen_geometry)
        print(f"Overlay initialized with geometry: {screen_geometry}")

        # 视窗参数
        self.rect_to_draw = None  # (x, y, w, h)
        self.anchor_to_draw = None  # (cx, cy)
        self.overlay_color = QColor(0, 0, 0, 160)
        self.border_color = QColor(0, 255, 0, 220)
        self.label_text = "导航监视区域"

    def set_geometry_and_show(self, center_x, center_y, size):
        """一步到位：设置几何参数并显示"""
        self.set_rect_and_show(
            center_x - size // 2,
            center_y - size // 2,
            size,
            size,
            anchor=(center_x, center_y)
        )

    def set_rect_and_show(self, left, top, width, height, anchor=None, label_text=None):
        """显示任意矩形监视区域，并将其余区域用半透明幕布遮罩。"""
        self.rect_to_draw = (
            int(left),
            int(top),
            max(1, int(width)),
            max(1, int(height))
        )
        self.anchor_to_draw = anchor
        if label_text is not None:
            self.label_text = label_text

        # 确保覆盖层是全屏的，以便在任何地方绘制
        screen_geometry = QApplication.primaryScreen().geometry()
        self.setGeometry(screen_geometry)

        self.show()
        self.raise_()
        self.update() # 强制重绘
        print(f"导航幕布已显示. Rect: {self.rect_to_draw}")

    def hide_overlay(self):
        """隐藏幕布"""
        self.hide()
        print("导航幕布已隐藏.")

    def paintEvent(self, event):
        """绘制事件"""
        if not self.rect_to_draw:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        x, y, w, h = self.rect_to_draw

        # 1. 绘制幕布，并在监视区域挖空
        overlay_path = QPainterPath()
        overlay_path.addRect(self.rect())
        hole_path = QPainterPath()
        hole_path.addRect(x, y, w, h)
        painter.fillPath(overlay_path.subtracted(hole_path), self.overlay_color)

        # 2. 绘制监视范围的方框 (绿色)
        pen_rect = QPen(self.border_color, 2)
        painter.setPen(pen_rect)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(x, y, w, h)

        # 3. 绘制锚点（中心点模式下用于确认截屏中心）
        if self.anchor_to_draw:
            pen_center = QPen(QColor(255, 80, 80), 3)
            painter.setPen(pen_center)
            cx, cy = self.anchor_to_draw
            painter.drawEllipse(cx - 3, cy - 3, 6, 6)

        # 4. 标签
        painter.setPen(QPen(Qt.green))
        painter.drawText(x, max(18, y - 8), self.label_text)
