"""
中心点选择覆盖层
用于在屏幕上选择人物位置作为截图中心点
"""

from PySide6.QtWidgets import QWidget, QApplication, QLabel
from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QPainter, QPen, QColor, QFont


class CenterPointSelector(QWidget):
    """中心点选择覆盖层，用于选择人物位置作为截图中心"""

    point_selected = Signal(int, int)  # center_x, center_y
    selection_cancelled = Signal()

    def __init__(self):
        super().__init__()

        # 窗口属性
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setFocusPolicy(Qt.StrongFocus)

        # 设置全屏
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)

        # 绘制状态
        self.selected_point = None
        self.hover_point = None

        # 设置光标
        self.setCursor(Qt.CrossCursor)

    def paintEvent(self, event):
        """绘制覆盖层"""
        painter = QPainter(self)

        # 半透明背景
        painter.fillRect(self.rect(), QColor(0, 0, 0, 120))

        # 绘制帮助文字
        painter.setPen(QPen(QColor(255, 255, 0), 2))
        painter.setFont(QFont("Arial", 14))
        painter.drawText(20, 40, "点击选择人物位置作为截图中心点")
        painter.drawText(20, 70, "按 ENTER 确认 | 按 ESC 取消")

        # 绘制十字准星
        if self.hover_point:
            self._draw_crosshair(painter, self.hover_point, QColor(255, 255, 0), 2)  # 黄色：悬停

        if self.selected_point:
            self._draw_crosshair(painter, self.selected_point, QColor(0, 255, 0), 3)  # 绿色：已选

    def _draw_crosshair(self, painter, point, color, width):
        """绘制十字准星"""
        painter.setPen(QPen(color, width))
        
        # 水平线
        painter.drawLine(
            point.x() - 30, point.y(),
            point.x() + 30, point.y()
        )
        
        # 垂直线
        painter.drawLine(
            point.x(), point.y() - 30,
            point.x(), point.y() + 30
        )
        
        # 中心圆圈
        painter.drawEllipse(point, 10, 10)

    def mouseMoveEvent(self, event):
        """鼠标移动"""
        self.hover_point = event.pos()
        self.update()

    def mousePressEvent(self, event):
        """鼠标点击 - 选择中心点"""
        if event.button() == Qt.LeftButton:
            self.selected_point = event.pos()
            self.update()

    def keyPressEvent(self, event):
        """键盘事件"""
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            # 确认选择
            if self.selected_point:
                self.point_selected.emit(
                    self.selected_point.x(),
                    self.selected_point.y()
                )
                self.close()
            else:
                # 如果没有选择点，使用当前鼠标位置
                cursor_pos = self.mapFromGlobal(QApplication.instance().cursor().pos())
                self.point_selected.emit(cursor_pos.x(), cursor_pos.y())
                self.close()

        elif event.key() == Qt.Key_Escape:
            # 取消
            self.selection_cancelled.emit()
            self.close()

        # 确保事件被处理
        super().keyPressEvent(event)

    def leaveEvent(self, event):
        """鼠标离开窗口"""
        self.hover_point = None
        self.update()
        super().leaveEvent(event)