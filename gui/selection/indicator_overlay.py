from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QPen, QColor, QBrush

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
            Qt.Tool | # 不在任务栏显示
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
        self.center_to_draw = None # (cx, cy)
        
    def set_geometry_and_show(self, center_x, center_y, size):
        """一步到位：设置几何参数并显示"""
        self.rect_to_draw = (
            center_x - size // 2,
            center_y - size // 2,
            size,
            size
        )
        self.center_to_draw = (center_x, center_y)
        
        # 确保覆盖层是全屏的，以便在任何地方绘制
        screen_geometry = QApplication.primaryScreen().geometry()
        self.setGeometry(screen_geometry)
        
        self.show()
        self.raise_()
        self.update() # 强制重绘
        print(f"导航幕布已显示. Center: {self.center_to_draw}, Size: {size}")

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
        
        # 1. 绘制监视范围的方框 (绿色)
        pen_rect = QPen(QColor(0, 255, 0), 2) # 2px 绿色
        painter.setPen(pen_rect)
        painter.setBrush(Qt.NoBrush)
        
        x, y, w, h = self.rect_to_draw
        painter.drawRect(x, y, w, h)
        
        # 2. 绘制中心点 (红色)
        if self.center_to_draw:
            pen_center = QPen(QColor(255, 0, 0), 3) # 3px 红色
            painter.setPen(pen_center)
            
            cx, cy = self.center_to_draw
            # 画一个3x3的小点
            painter.drawPoint(cx, cy)

        # 3. (可选) 在左上角绘制标签
        painter.setPen(QPen(Qt.green))
        painter.drawText(x, y - 5, f"导航监控中...")
