import sys
from auto_modules.paths import data_root
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QStackedWidget, QApplication
)
from PySide6.QtCore import Qt

from .app_context import AppContext
from .theme import app_stylesheet
from .modes.mapping_widget import MappingWidget
from .modes.navigation import NavigationModeWidget
from .modes.map_editor import MapEditorWidget
from .modes.follow import FollowPage
from .modes.events import EventWorkbenchPage
from .modes.lan import LanPage
from .dialogs.perception import PerceptionWorkbenchDialog
from .gamepad.host_manager import GamepadHostManager
from auto_modules.ui.virtual_gamepad.gamepad_page import GamepadPage


GAMEPAD_CONFIG_ROOT = data_root() / "virtual_gamepad" / "configs"

class MainWindow(QMainWindow):
    """主应用程序窗口，负责模式切换和UI骨架。"""

    def __init__(self, *, gamepad_host_manager: GamepadHostManager | None = None):
        super().__init__()
        self.setWindowTitle("auto_modules · 实时小地图拼接系统")
        self.setGeometry(80, 80, 1100, 760)
        self.setMinimumSize(460, 520)
        self.setStyleSheet(app_stylesheet())

        # 1. 创建核心上下文
        self.app_context = AppContext(self)
        self.gamepad_host_manager = gamepad_host_manager or GamepadHostManager()
        self.gamepad_host_start_result = self.gamepad_host_manager.start()
        self._gamepad_close_requested = False
        self._gamepad_close_approved = False
        self._runtimes_stopped = False

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
        self.mode_btn_mapping.setProperty("role", "mode")
        self.mode_btn_mapping.setCheckable(True)
        self.mode_btn_mapping.setChecked(True)
        self.mode_btn_mapping.clicked.connect(lambda: self.switch_mode(0))

        self.mode_btn_nav = QPushButton("🧭 导航模式")
        self.mode_btn_nav.setProperty("role", "mode")
        self.mode_btn_nav.setCheckable(True)
        self.mode_btn_nav.clicked.connect(lambda: self.switch_mode(1))

        self.mode_btn_gamepad = QPushButton("🎮 虚拟手柄")
        self.mode_btn_gamepad.setProperty("role", "mode")
        self.mode_btn_gamepad.setCheckable(True)
        self.mode_btn_gamepad.clicked.connect(lambda: self.switch_mode(2))

        self.mode_btn_map_editor = QPushButton("🧱 地图编辑")
        self.mode_btn_map_editor.setProperty("role", "mode")
        self.mode_btn_map_editor.setCheckable(True)
        self.mode_btn_map_editor.clicked.connect(lambda: self.switch_mode(3))

        self.mode_btn_follow = QPushButton("事件工作台")
        self.mode_btn_follow.setProperty("role", "mode")
        self.mode_btn_follow.setCheckable(True)
        self.mode_btn_follow.clicked.connect(lambda: self.switch_mode(5))

        self.mode_btn_lan = QPushButton("局域网")
        self.mode_btn_lan.setProperty("role", "mode")
        self.mode_btn_lan.setCheckable(True)
        self.mode_btn_lan.clicked.connect(lambda: self.switch_mode(6))

        self.mode_buttons = [
            self.mode_btn_mapping,
            self.mode_btn_nav,
            self.mode_btn_gamepad,
            self.mode_btn_map_editor,
            self.mode_btn_follow,
            self.mode_btn_lan,
        ]
        mode_layout.addWidget(self.mode_btn_mapping)
        mode_layout.addWidget(self.mode_btn_nav)
        mode_layout.addWidget(self.mode_btn_gamepad)
        mode_layout.addWidget(self.mode_btn_map_editor)
        mode_layout.addWidget(self.mode_btn_follow)
        mode_layout.addWidget(self.mode_btn_lan)
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

        # Driver and physical-input interception stay in the independent Host.
        # This workbench page owns only profiles, controls, and visible status.
        self.gamepad_page = GamepadPage(
            self.gamepad_host_manager.create_client(),
            profile_root=GAMEPAD_CONFIG_ROOT,
            parent=self,
            client_factory=self.gamepad_host_manager.create_client,
        )
        self.gamepad_page.shutdown_finished.connect(self._on_gamepad_shutdown_finished)
        self.stacked_widget.addWidget(self.gamepad_page)
        if not self.gamepad_host_start_result.connected:
            self.gamepad_page.show_host_error(self.gamepad_host_start_result.message)

        self.map_editor_widget = MapEditorWidget(source_file=__file__, parent=self)
        self.stacked_widget.addWidget(self.map_editor_widget)

        self.follow_page = FollowPage(parent=self)
        self.follow_page.open_lan_requested.connect(lambda: self.switch_mode(2))
        self.stacked_widget.addWidget(self.follow_page)
        self.event_workbench = EventWorkbenchPage(parent=self)
        self.stacked_widget.addWidget(self.event_workbench)
        self.lan_page = LanPage(self.gamepad_host_manager.create_client, parent=self)
        self.stacked_widget.addWidget(self.lan_page)

        self.perception_button = QPushButton("Perception")
        self.perception_button.setToolTip("Edit reusable detection profiles and test them on screenshots")
        self.perception_button.clicked.connect(self.open_perception_workbench)
        mode_layout.addWidget(self.perception_button)
        self.perception_dialog = None

        main_layout.addWidget(self.stacked_widget)

        self.switch_mode(0) # 默认进入绘图模式

    def switch_mode(self, index):
        """切换UI模式"""
        self.stacked_widget.setCurrentIndex(index)
        for i, btn in enumerate(self.mode_buttons):
            btn.setChecked(i == index)
            btn.setEnabled(True)

        if index == 1:
            self.nav_widget.refresh_map_list()
        elif index == 3:
            self.map_editor_widget.refresh_map_list()

    def closeEvent(self, event):
        """关闭窗口时确保所有子进程和定时器都停止"""
        if self._gamepad_close_approved:
            event.accept()
            return

        # Do not let Qt tear down its event loop while reset/pause work is
        # still in flight: the independent Host would otherwise be able to
        # keep bound physical keys locked after this window disappears.
        event.ignore()
        if self._gamepad_close_requested:
            return
        self._gamepad_close_requested = True
        self.setEnabled(False)
        if not self._runtimes_stopped:
            self._runtimes_stopped = True
            self.mapping_widget.stop_runtime()
            self.nav_widget.stop_runtime()
            self.follow_page.stop_runtime()
            self.lan_page.shutdown()
            self.event_workbench.shutdown()
            if self.perception_dialog is not None:
                self.perception_dialog.close()
        self.gamepad_page.shutdown()

    def _on_gamepad_shutdown_finished(self, page_succeeded: bool, page_message: str) -> None:
        """Only complete close after virtual-input cleanup is confirmed safe."""
        host_result = self.gamepad_host_manager.shutdown()
        safe_to_close = page_succeeded or host_result.succeeded or host_result.stopped_owned_host
        if not safe_to_close:
            self._gamepad_close_requested = False
            self.setEnabled(True)
            message = page_message or "; ".join(host_result.errors) or "Virtual gamepad cleanup could not be confirmed."
            self.gamepad_page.show_host_error(f"Close cancelled: {message} Retry after the Host is available.")
            return
        self._gamepad_close_approved = True
        self.setEnabled(True)
        self.close()

    def open_perception_workbench(self):
        """Open the independent perception profile editor."""
        if self.perception_dialog is None:
            self.perception_dialog = PerceptionWorkbenchDialog(self)
            self.perception_dialog.finished.connect(self._clear_perception_dialog)
        self.perception_dialog.show()
        self.perception_dialog.raise_()
        self.perception_dialog.activateWindow()

    def _clear_perception_dialog(self, _result: int) -> None:
        self.perception_dialog = None

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
