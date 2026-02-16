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
        self.viewport_size = (200, 200) # 默认大小
        self.center_pos = (screen_geometry.width() // 2, screen_geometry.height() // 2)
        self.center_offset_y = 0 # 额外的 Y 轴偏移
        
        # 可见性控制
        self.is_visible = False
        
    def set_viewport(self, size):
        """设置视窗大小 (宽, 高)"""
        self.viewport_size = size
        self.update() # 触发重绘
        
    def set_center(self, center):
        """设置视窗中心 (x, y)"""
        self.center_pos = center
        self.update()
        
    def show_overlay(self):
        # 重新获取屏幕尺寸 (以防分辨率变化)
        screen_geometry = QApplication.primaryScreen().geometry()
        self.setGeometry(screen_geometry)
        self.is_visible = True
        self.show()
        self.raise_()
        self.update()
        print(f"Overlay shown. Geometry: {self.geometry()}, Visible: {self.isVisible()}")
        
    def hide_overlay(self):
        self.is_visible = False
        self.hide()
        
    def paintEvent(self, event):
        if not self.is_visible:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制全屏透明背景 (调试用，微弱的红色)
        # painter.fillRect(self.rect(), QColor(255, 0, 0, 10))
        
        w, h = self.viewport_size
        cx, cy = self.center_pos
        
        # 绘制绿色矩形框 (真实游戏视野)
        # 线宽 3px，绿色实线
        pen = QPen(QColor(0, 255, 0), 3)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        
        # 计算左上角坐标
        x = cx - w // 2
        y = cy - h // 2
        
        painter.drawRect(x, y, w, h)
        
        # 绘制中心十字准星 (辅助对齐)
        pen_cross = QPen(QColor(0, 255, 0, 100), 1) # 半透明
        painter.setPen(pen_cross)
        painter.drawLine(cx - 10, cy, cx + 10, cy)
        painter.drawLine(cx, cy - 10, cx, cy + 10)
        
        # 绘制文字标签
        painter.setPen(QPen(Qt.green))
        painter.drawText(x, y - 5, f"Game Viewport ({w}x{h})")
