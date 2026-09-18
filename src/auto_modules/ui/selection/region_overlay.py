"""
透明覆盖层
用于在屏幕上画框选择小地图区域
"""

from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtCore import Qt, Signal, QRect, QPoint
from PySide6.QtGui import QPainter, QPen, QColor


class TransparentOverlay(QWidget):
    """透明覆盖层，用于在屏幕上画框选择区域"""
    
    region_selected = Signal(int, int, int, int)  # x, y, width, height
    
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
        self.drawing = False
        self.start_point = None
        self.end_point = None
        self.current_rect = None
        
        # 设置光标
        self.setCursor(Qt.CrossCursor)
        
        # 提示文字
        self.show_help = True
        
        # 新增：交互模式开关
        self.interactive = True
        # 新增：背景绘制开关
        self.draw_background = True

    def set_interactive(self, is_interactive: bool):
        """设置是否为交互模式"""
        self.interactive = is_interactive
        if is_interactive:
            self.setCursor(Qt.CrossCursor)
            self.setFocusPolicy(Qt.StrongFocus)
            self.show_help = True
        else:
            self.setCursor(Qt.ArrowCursor)
            self.setFocusPolicy(Qt.NoFocus)
            self.show_help = False
        self.update()

    def set_draw_background(self, enabled: bool):
        """设置是否绘制半透明背景"""
        self.draw_background = enabled
        self.update()
    
    def paintEvent(self, event):
        """绘制覆盖层"""
        painter = QPainter(self)
        
        # 根据开关决定是否绘制半透明背景
        if self.draw_background:
            painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
        
        # 绘制帮助文字
        if self.show_help:
            painter.setPen(QPen(QColor(255, 255, 0), 2))
            painter.drawText(20, 40, "鼠标拖动画框选择小地图区域")
            painter.drawText(20, 70, "按 ENTER 确认 | 按 ESC 取消 | 按 R 重置")
        
        # 绘制选择框
        if self.start_point and self.end_point:
            rect = QRect(self.start_point, self.end_point).normalized()
            
            # 选中区域透明（显示游戏画面）
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillRect(rect, QColor(0, 0, 0, 0))
            
            # 绘制边框
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            if self.drawing:
                painter.setPen(QPen(QColor(255, 255, 0), 3))  # 黄色：正在画
            else:
                painter.setPen(QPen(QColor(0, 255, 0), 3))    # 绿色：完成
            painter.drawRect(rect)
            
            # 显示尺寸
            width = rect.width()
            height = rect.height()
            text = f"{width} x {height}"
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.drawText(rect.x(), rect.y() - 10, text)
            
            self.current_rect = rect
    
    def mousePressEvent(self, event):
        """鼠标按下"""
        if not self.interactive:
            return
        if event.button() == Qt.LeftButton:
            self.drawing = True
            self.start_point = event.pos()
            self.end_point = event.pos()
            self.show_help = False
            self.update()
    
    def mouseMoveEvent(self, event):
        """鼠标移动"""
        if not self.interactive:
            return
        if self.drawing:
            self.end_point = event.pos()
            self.update()
    
    def mouseReleaseEvent(self, event):
        """鼠标释放"""
        if not self.interactive:
            return
        if event.button() == Qt.LeftButton:
            self.drawing = False
            self.end_point = event.pos()
            self.update()
    
    def keyPressEvent(self, event):
        """键盘事件"""
        if not self.interactive:
            return
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            # 确认选择
            if self.current_rect:
                self.region_selected.emit(
                    self.current_rect.x(),
                    self.current_rect.y(),
                    self.current_rect.width(),
                    self.current_rect.height()
                )
                self.close()
            else:
                # 如果没有选择区域，尝试使用当前鼠标位置创建一个小区域
                cursor_pos = self.mapFromGlobal(QApplication.instance().cursor().pos())
                if self.start_point is None:
                    self.start_point = cursor_pos
                    self.end_point = QPoint(cursor_pos.x() + 100, cursor_pos.y() + 100)
                    self.current_rect = QRect(self.start_point, self.end_point).normalized()
                
                self.region_selected.emit(
                    self.current_rect.x(),
                    self.current_rect.y(),
                    self.current_rect.width(),
                    self.current_rect.height()
                )
                self.close()
        
        elif event.key() == Qt.Key_Escape:
            # 取消
            self.close()
        
        elif event.key() == Qt.Key_R:
            # 重置
            self.start_point = None
            self.end_point = None
            self.current_rect = None
            self.show_help = True
            self.update()
        
        # 确保事件被处理
        super().keyPressEvent(event)
