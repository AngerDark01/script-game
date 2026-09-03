import sys
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QStackedWidget, QApplication
)
from PySide6.QtCore import Qt

from .app_context import AppContext
from .modes.mapping_widget import MappingWidget
from .modes.navigation import NavigationModeWidget

class MainWindow(QMainWindow):
    """主应用程序窗口，负责模式切换和UI骨架。"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("实时小地图拼接系统")
        self.setGeometry(80, 80, 1100, 760)

        # 1. 创建核心上下文
        self.app_context = AppContext(self)

        # 2. 设置UI
        self.setup_ui()

        # 3. 设置窗口始终保持在最顶层
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

    def setup_ui(self):
        """设置主UI骨架"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)

        # 模式切换按钮
        mode_layout = QHBoxLayout()
        self.mode_btn_mapping = QPushButton("🗺️ 绘图模式")
        self.mode_btn_mapping.setCheckable(True)
        self.mode_btn_mapping.setChecked(True)
        self.mode_btn_mapping.clicked.connect(lambda: self.switch_mode(0))

        self.mode_btn_nav = QPushButton("🧭 导航模式")
        self.mode_btn_nav.setCheckable(True)
        self.mode_btn_nav.clicked.connect(lambda: self.switch_mode(1))

        self.mode_buttons = [self.mode_btn_mapping, self.mode_btn_nav]
        mode_layout.addWidget(self.mode_btn_mapping)
        mode_layout.addWidget(self.mode_btn_nav)
        mode_layout.addStretch()
        main_layout.addLayout(mode_layout)

        # 堆叠窗口区域
        self.stacked_widget = QStackedWidget()

        # 绘图模式页面
        self.mapping_widget = MappingWidget(self.app_context, self)
        self.stacked_widget.addWidget(self.mapping_widget)

        # 导航模式页面
        # 注意：NavigationModeWidget的__init__也需要修改以接收app_context
        self.nav_widget = NavigationModeWidget(self.app_context, self)
        self.stacked_widget.addWidget(self.nav_widget)

        main_layout.addWidget(self.stacked_widget)

        self.switch_mode(0) # 默认进入绘图模式

    def switch_mode(self, index):
        """切换UI模式"""
        self.stacked_widget.setCurrentIndex(index)
        for i, btn in enumerate(self.mode_buttons):
            btn.setChecked(i == index)
            btn.setEnabled(i != index)

        if index == 1:
            self.nav_widget.refresh_map_list()

    def closeEvent(self, event):
        """关闭窗口时确保所有子进程和定时器都停止"""
        self.mapping_widget.stop_runtime()
        self.nav_widget.stop_runtime()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
