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
from .modes.torchlight.follow import FollowPage
from .modes.torchlight.navigation import build_torchlight_navigation_composition
from .modes.poe2 import build_poe2_live_terrain_composition
from .modes.events import EventWorkbenchPage
from .modes.lan import LanPage
from .modes.poe2_live_terrain import Poe2LiveTerrainPage
from .dialogs.perception import PerceptionWorkbenchDialog
from .gamepad.host_manager import GamepadHostManager
from auto_modules.ui.virtual_gamepad.gamepad_page import GamepadPage
from auto_modules.adapters.host.communication_adapter import HostCommunicationAdapter
from auto_modules.application.communication.manager import CommunicationManager
from auto_modules.ui.composition import create_communication_services


GAMEPAD_CONFIG_ROOT = data_root() / "virtual_gamepad" / "configs"

class MainWindow(QMainWindow):
    """主应用程序窗口，负责模式切换和UI骨架。"""

    def __init__(
        self,
        *,
        gamepad_host_manager: GamepadHostManager | None = None,
        communication_manager: CommunicationManager | None = None,
        communication_adapter: HostCommunicationAdapter | None = None,
    ):
        super().__init__()
        self.setWindowTitle("auto_modules · 实时小地图拼接系统")
        self.setGeometry(80, 80, 1100, 760)
        self.setMinimumSize(460, 520)
        self.setStyleSheet(app_stylesheet())

        # 1. 创建核心上下文
        self.app_context = AppContext(self)
        self.gamepad_host_manager = gamepad_host_manager or GamepadHostManager()
        self.gamepad_host_start_result = self.gamepad_host_manager.start()
        # All embedded business pages receive this process-scoped runtime. The
        # adapter owns the single Host client used for logical peer sessions;
        # pages only request capability leases from the manager.
        self.communication_adapter = communication_adapter
        self.communication_manager = communication_manager
        self._owns_communication_adapter = False
        self._owns_communication_manager = False
        if self.communication_adapter is None and self.communication_manager is None:
            services = create_communication_services(self.gamepad_host_manager.create_client)
            self.communication_adapter = services.adapter
            self.communication_manager = services.manager
            self._owns_communication_adapter = True
            self._owns_communication_manager = True
        elif self.communication_manager is None and self.communication_adapter is not None:
            self.communication_manager = CommunicationManager(self.communication_adapter.transport)
            self._owns_communication_manager = True
        elif self.communication_manager is not None:
            runtime_adapter = getattr(self.communication_manager.transport, "adapter", None)
            if self.communication_adapter is None:
                self.communication_adapter = runtime_adapter
            elif runtime_adapter is not None and self.communication_adapter is not runtime_adapter:
                raise ValueError("communication manager and adapter must share one transport")
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

        self.mode_btn_poe2_terrain = QPushButton("🎮 PoE2 地形")
        self.mode_btn_poe2_terrain.setProperty("role", "mode")
        self.mode_btn_poe2_terrain.setCheckable(True)
        self.mode_btn_poe2_terrain.clicked.connect(lambda: self.switch_mode(7))

        self.mode_buttons = [
            self.mode_btn_mapping,
            self.mode_btn_nav,
            self.mode_btn_gamepad,
            self.mode_btn_map_editor,
            self.mode_btn_follow,
            self.mode_btn_lan,
            self.mode_btn_poe2_terrain,
        ]
        mode_layout.addWidget(self.mode_btn_mapping)
        mode_layout.addWidget(self.mode_btn_nav)
        mode_layout.addWidget(self.mode_btn_gamepad)
        mode_layout.addWidget(self.mode_btn_map_editor)
        mode_layout.addWidget(self.mode_btn_follow)
        mode_layout.addWidget(self.mode_btn_lan)
        mode_layout.addWidget(self.mode_btn_poe2_terrain)
        mode_layout.addStretch()
        main_layout.addLayout(mode_layout)

        # 堆叠窗口区域
        self.stacked_widget = QStackedWidget()

        # 绘图模式页面
        self.mapping_widget = MappingWidget(self.app_context, self)
        self.stacked_widget.addWidget(self.mapping_widget)

        # 导航模式页面
        # 注意：NavigationModeWidget的__init__也需要修改以接收app_context
        torchlight_navigation = build_torchlight_navigation_composition()
        self.nav_widget = NavigationModeWidget(
            self.app_context,
            self,
            event_registry_factory=torchlight_navigation.event_registry_factory,
            game_window_finder=torchlight_navigation.game_window_finder,
            event_overlay_providers=torchlight_navigation.event_overlay_providers,
        )
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

        self.follow_page = FollowPage(
            parent=self,
            communication_manager=self.communication_manager,
        )
        self.follow_page.open_lan_requested.connect(lambda: self.switch_mode(2))
        self.stacked_widget.addWidget(self.follow_page)
        self.event_workbench = EventWorkbenchPage(
            parent=self,
            communication_manager=self.communication_manager,
            communication_adapter=self.communication_adapter,
        )
        self.stacked_widget.addWidget(self.event_workbench)
        self.lan_page = LanPage(self.gamepad_host_manager.create_client, parent=self)
        self.stacked_widget.addWidget(self.lan_page)

        poe2_live_terrain = build_poe2_live_terrain_composition(
            screen_capture=self.app_context.screen_capture,
            recognizer=self.app_context.recognizer,
        )
        self.poe2_terrain_page = Poe2LiveTerrainPage(
            service=poe2_live_terrain.service,
            runtime=poe2_live_terrain.runtime,
            config_store=poe2_live_terrain.config_store,
            parent=self,
        )
        self.stacked_widget.addWidget(self.poe2_terrain_page)

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
        mode_indices = (0, 1, 2, 3, 5, 6, 7)
        for button_index, btn in zip(mode_indices, self.mode_buttons):
            btn.setChecked(button_index == index)
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
            self.poe2_terrain_page.shutdown()
            if self._owns_communication_manager and self.communication_manager is not None:
                self.communication_manager.close()
            if self._owns_communication_adapter and self.communication_adapter is not None:
                self.communication_adapter.close()
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
