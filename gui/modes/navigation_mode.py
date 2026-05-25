"""
导航模式模块 - 提供游戏内自动导航功能的主界面

本模块实现了基于地图匹配的玩家位置实时定位和导航功能，
支持手动设置初始位置、自动路径跟踪、屏幕中心校准等功能。
"""

import time
import cv2
import numpy as np
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QComboBox, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
    QMessageBox, QGraphicsPathItem, QCheckBox, QApplication
)
from PySide6.QtCore import Qt, QTimer, QPointF, QEvent, QPoint
from PySide6.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QBrush, QPainterPath

from core.navigation_tasks.controller import NavigationTaskController
from core.navigation_tasks.models import NavigationIntentType
from core.navigation_core import NavigationCore
from core.motion_controller import MotionController
from core.route_manager import RouteManager
from core.events.debug import event_log, start_event_log_session
from core.events.capture_provider import GameWindowCaptureProvider
from core.events.config import load_event_config, save_event_config
from core.events.coordinator import EventCoordinator
from ..selection.indicator_overlay import OverlayWindow
from ..selection.center_selector import CenterPointSelector
from ..dialogs.event_manager_dialog import EventManagerDialog
from ..dialogs.nav_params_dialog import NavParametersDialog
from ..navigation_params import NavConfig
from .event_test_controller import ManualEventTestController
from .navigation.event_adapter import (
    build_event_tick,
    create_default_event_registry,
    event_config_summary,
    event_status_text,
    find_default_game_window_rect,
)
from .navigation.event_overlay import (
    clear_event_overlay,
    global_to_scene,
    render_event_overlay,
)
from .navigation.map_runtime import (
    MISSING_MAP_DATA_LABEL,
    build_capture_geometry,
    list_map_names,
    load_nav_config,
    physical_center_from_logical,
    resolve_map_folder,
    save_default_nav_config,
    save_nav_config,
)
from .navigation.route_overlay import clear_route_overlay, render_route_overlay
from .navigation.viewport_overlay import (
    game_view_scene_rect,
    monitor_scene_rect,
    screen_overlay_geometry,
)

class NavigationModeWidget(QWidget):
    """
    导航模式主窗口组件

    提供完整的导航功能界面，包括：
    - 地图加载和显示
    - 玩家实时位置定位
    - 导航参数配置
    - 自动移动控制
    - 屏幕中心校准
    """

    def __init__(self, app_context, main_window):
        """
        初始化导航模式窗口

        创建并初始化导航模式的所有组件，包括：
        - 导航核心引擎 (NavigationCore)
        - 运动控制器 (MotionController)
        - 调试幕布覆盖窗口 (OverlayWindow)
        - 导航配置参数 (NavConfig)
        - 参数配置对话框 (NavParametersDialog)
        - 导航循环定时器 (QTimer)

        参数:
            app_context (dict): 应用程序上下文，包含共享资源和服务，
                               如屏幕截图服务 (screen_capture) 等
            main_window (QWidget): 主窗口引用，用于对话框的父级管理，
                                  确保对话框在主窗口之上显示

        返回:
            无

        异常:
            无直接异常，但依赖的组件初始化失败可能导致后续操作异常
        """
        super().__init__()
        self.app_context = app_context  # 保存应用程序上下文，用于访问屏幕截图等服务
        self.main_window = main_window  # 保留用于对话框的父级管理
        self.nav_core = None  # 导航核心引擎实例，负责地图定位和路径计算
        self.motion_controller = MotionController()  # 运动控制器，用于模拟键盘输入实现自动移动
        self.overlay = OverlayWindow()  # 调试幕布覆盖窗口，用于可视化显示监控区域
        self.nav_config = NavConfig()  # 使用数据类管理导航配置参数，包含所有导航相关设置
        self.map_folder_path = None  # 当前加载地图的文件夹路径，用于保存配置文件
        self.params_dialog = NavParametersDialog(self)  # 导航参数配置对话框，允许用户调整参数
        self.event_dialog = None

        self.init_ui()  # 初始化用户界面，创建所有 UI 控件
        self._connect_signals()  # 连接 UI 控件的信号到对应的槽函数

        self.nav_timer = QTimer()  # 导航循环定时器，按固定频率执行定位和移动
        self.nav_timer.timeout.connect(self.navigation_loop)  # 连接定时器超时信号到导航循环函数

        # 缓存物理坐标，避免每次循环重复计算
        # 存储格式：(center_x, center_y)，单位为物理像素
        self._capture_center_physical = None
        self._current_capture_rect = None
        self._current_player_local_pos = None
        self.route_manager = RouteManager()
        self.route_data = None
        self.navigation_task_controller = NavigationTaskController()
        self.auto_navigation_enabled = False
        self.map_click_mode = "NONE"
        self.route_overlay_items = []
        self.route_path_item = None
        self.game_view_rect_item = None
        self._game_input_window_mode = False
        self._main_window_was_topmost = False
        self.event_registry = create_default_event_registry()
        self.event_config = None
        self.event_coordinator = None
        self.event_capture_provider = None
        self.event_overlay_items = []
        self._event_arbitration_last_log_ms = 0
        self._ensure_event_dialog()
        self.portal_test_controller = ManualEventTestController(
            self.event_dialog.test_portal_button if self.event_dialog else None,
            "测试传送门",
            "停止传送门测试",
        )

    def init_ui(self):
        """
        初始化用户界面布局

        创建并布局所有 UI 组件，包括：
        - 顶部控制栏：地图选择下拉框、加载按钮、功能按钮（设置初始位置、开始导航、自动移动开关、校准屏幕中心、参数面板）
        - 图形视图：QGraphicsView 用于显示地图和玩家位置标记
        - 状态栏：显示当前操作状态和定位信息

        布局结构:
            QVBoxLayout (主布局)
            ├── QHBoxLayout (顶部控制栏)
            │   ├── QLabel ("选择地图:")
            │   ├── QComboBox (地图选择)
            │   ├── QPushButton (加载地图)
            │   ├── QPushButton (设置初始位置)
            │   ├── QPushButton (开始/停止导航)
            │   ├── QCheckBox (启用自动移动)
            │   ├── QPushButton (校准屏幕中心)
            │   └── QPushButton (参数面板)
            ├── QGraphicsView (地图显示区域)
            └── QLabel (状态栏)

        返回:
            无

        异常:
            无直接异常
        """
        layout = QVBoxLayout(self)  # 创建垂直布局作为主布局

        # --- 顶部控制栏 ---
        top_bar = QHBoxLayout()  # 创建水平布局用于顶部控制栏

        self.map_combo = QComboBox()  # 地图选择下拉框，用于选择要加载的地图
        self.refresh_map_list()  # 刷新地图列表，从 map_data 文件夹读取可用地图
        top_bar.addWidget(QLabel("选择地图:"))  # 添加标签
        top_bar.addWidget(self.map_combo, 1)  # 添加下拉框，拉伸因子为 1 使其占据剩余空间

        self.btn_load = QPushButton("加载地图")  # 加载选中地图的按钮
        top_bar.addWidget(self.btn_load)

        self.btn_hint = QPushButton("📍 设置初始位置")  # 设置初始位置提示按钮，用于手动指定玩家初始位置
        self.btn_hint.setCheckable(True)  # 设置为可切换状态（按下/弹起）
        self.btn_hint.setEnabled(False)  # 初始禁用，加载地图后启用
        top_bar.addWidget(self.btn_hint)

        self.btn_start = QPushButton("开始导航")  # 开始/停止导航按钮，可切换状态
        self.btn_start.setCheckable(True)  # 设置为可切换状态
        self.btn_start.setEnabled(False)  # 初始禁用，加载地图后启用
        top_bar.addWidget(self.btn_start)
        self.btn_set_exit = QPushButton("设置出口")
        self.btn_set_exit.setCheckable(True)
        self.btn_set_exit.setEnabled(False)
        top_bar.addWidget(self.btn_set_exit)

        self.btn_add_required = QPushButton("添加必经点")
        self.btn_add_required.setCheckable(True)
        self.btn_add_required.setEnabled(False)
        top_bar.addWidget(self.btn_add_required)

        self.btn_undo_required = QPushButton("撤销必经点")
        self.btn_undo_required.setEnabled(False)
        top_bar.addWidget(self.btn_undo_required)

        self.btn_add_guide = QPushButton("添加途经点")
        self.btn_add_guide.setCheckable(True)
        self.btn_add_guide.setEnabled(False)
        top_bar.addWidget(self.btn_add_guide)

        self.btn_undo_guide = QPushButton("撤销途经点")
        self.btn_undo_guide.setEnabled(False)
        top_bar.addWidget(self.btn_undo_guide)

        self.btn_clear_route = QPushButton("清空路线")
        self.btn_clear_route.setEnabled(False)
        top_bar.addWidget(self.btn_clear_route)

        self.btn_save_route = QPushButton("保存路线")
        self.btn_save_route.setEnabled(False)
        top_bar.addWidget(self.btn_save_route)

        self.btn_auto_nav = QPushButton("开始自动到出口")
        self.btn_auto_nav.setCheckable(True)
        self.btn_auto_nav.setEnabled(False)
        top_bar.addWidget(self.btn_auto_nav)



        self.calibrate_button = QPushButton("校准屏幕中心")  # 屏幕中心校准按钮，用于确定游戏窗口的中心点坐标
        top_bar.addWidget(self.calibrate_button)

        self.params_button = QPushButton("⚙️ 参数面板")  # 打开参数配置面板按钮
        top_bar.addWidget(self.params_button)
        self.event_button = QPushButton("事件管理")
        top_bar.addWidget(self.event_button)
        layout.addLayout(top_bar)  # 将顶部控制栏添加到主布局

        # --- 图形视图 ---
        self.scene = QGraphicsScene()  # QGraphics 场景，用于承载地图和标记项
        self.scene.installEventFilter(self)  # 安装事件过滤器以捕获鼠标点击事件
        self.view = QGraphicsView(self.scene)  # 图形视图，用于显示场景内容
        self.view.setRenderHint(QPainter.Antialiasing)  # 启用抗锯齿渲染，使图形显示更平滑
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)  # 设置拖拽模式为手形拖拽，允许用户拖拽查看地图
        layout.addWidget(self.view)  # 将图形视图添加到主布局

        # --- 图形项 ---
        self.map_item = None  # 地图图片项，用于显示拼接后的完整地图
        self.last_pos_item = None  # 上次退出位置标记项，用紫色圆点表示绘图模式保存的最后位置
        self.hint_item = None  # 初始位置提示标记项，用蓝色圆点表示用户点击的初始大致位置
        self.player_item = None  # 玩家位置标记项，用红色圆点表示当前实时定位的玩家位置
        self.target_item = None  # 目标位置标记项，用绿色方块表示点击的目标位置
        self.monitor_rect_item = None  # 监控区域矩形框项，用绿色半透明框表示屏幕截图区域
        self.game_view_rect_item = None  # 真实主画面可见/可交互范围框，独立于小地图截图范围
        self.path_item = None  # 路径显示项（暂未使用），用于显示导航路径

        # --- 状态栏 ---
        self.status_label = QLabel("请选择并加载地图")  # 状态信息显示标签，显示当前操作状态和定位结果
        layout.addWidget(self.status_label)  # 将状态栏添加到主布局



    def _connect_signals(self):
        """
        连接所有 UI 控件的信号到对应的槽函数

        建立的信号连接包括:
        - 按钮点击信号 -> 对应功能函数
        - 复选框状态变化信号 -> 自动移动切换函数
        - 参数对话框的参数变化信号 -> 参数更新函数
        - 参数对话框的保存信号 -> 配置保存函数
        - 参数对话框的幕布切换信号 -> 幕布显示切换函数

        返回:
            无

        异常:
            无直接异常
        """
        # 连接按钮点击信号
        self.btn_load.clicked.connect(self.load_map)  # 加载地图按钮 -> load_map 函数
        self.btn_hint.clicked.connect(self.toggle_hint_mode)  # 设置初始位置按钮 -> toggle_hint_mode 函数
        self.btn_start.clicked.connect(self.toggle_navigation)  # 开始/停止导航按钮 -> toggle_navigation 函数
        self.btn_set_exit.clicked.connect(self.toggle_exit_mode)
        self.btn_add_required.clicked.connect(self.toggle_required_mode)
        self.btn_undo_required.clicked.connect(self.undo_required_point)
        self.btn_add_guide.clicked.connect(self.toggle_guide_mode)
        self.btn_undo_guide.clicked.connect(self.undo_guide_point)
        self.btn_clear_route.clicked.connect(self.clear_route)
        self.btn_save_route.clicked.connect(self.save_route)
        self.btn_auto_nav.clicked.connect(self.toggle_auto_navigation)

        self.params_button.clicked.connect(self.toggle_params_dialog)  # 参数面板按钮 -> toggle_params_dialog 函数
        self.event_button.clicked.connect(self.toggle_event_dialog)
        self.calibrate_button.clicked.connect(self._calibrate_screen_center)  # 校准按钮 -> _calibrate_screen_center 函数

        # 连接参数对话框的信号
        self.params_dialog.parameters_changed.connect(self._on_parameter_changed)  # 参数变化信号 -> _on_parameter_changed 函数
        self.params_dialog.save_requested.connect(self._save_nav_config)  # 保存请求信号 -> _save_nav_config 函数
        self.params_dialog.save_default_requested.connect(self._save_nav_default_config)
        self.params_dialog.nav_toggle_overlay_btn.clicked.connect(self._toggle_overlay_display)  # 幕布切换按钮 -> _toggle_overlay_display 函数
        self._connect_event_dialog_signals()

    def _ensure_event_dialog(self) -> EventManagerDialog:
        if self.event_dialog is not None:
            return self.event_dialog
        self.event_dialog = EventManagerDialog(self.main_window or self)
        self._connect_event_dialog_signals()
        if hasattr(self, "portal_test_controller"):
            self.portal_test_controller.button = self.event_dialog.test_portal_button
            self.portal_test_controller.reset_button()
        if self.event_registry and self.event_config is not None:
            self._refresh_event_dialog()
        return self.event_dialog

    def _connect_event_dialog_signals(self) -> None:
        if not self.event_dialog:
            return
        try:
            self.event_dialog.config_changed.disconnect(self._on_event_config_changed)
        except (RuntimeError, TypeError):
            pass
        try:
            self.event_dialog.save_requested.disconnect(self._save_event_config)
        except (RuntimeError, TypeError):
            pass
        try:
            self.event_dialog.test_portal_requested.disconnect(self._run_portal_manual_test)
        except (RuntimeError, TypeError):
            pass
        try:
            self.event_dialog.reset_portal_requested.disconnect(self._reset_portal_event_state)
        except (RuntimeError, TypeError):
            pass
        self.event_dialog.config_changed.connect(self._on_event_config_changed)
        self.event_dialog.save_requested.connect(self._save_event_config)
        self.event_dialog.test_portal_requested.connect(self._run_portal_manual_test)
        self.event_dialog.reset_portal_requested.connect(self._reset_portal_event_state)

    def toggle_params_dialog(self):
        """
        切换参数配置对话框的显示/隐藏状态

        如果对话框当前在前台则隐藏，否则显示并前置对话框。
        用于响应用户点击"参数面板"按钮的操作。

        返回:
            无

        异常:
            无
        """
        if self._toggle_owned_dialog(self.params_dialog):
            self.params_dialog.hide()

    def toggle_event_dialog(self):
        self._ensure_event_dialog()
        self._refresh_event_dialog()
        if self._toggle_owned_dialog(self.event_dialog):
            self.event_dialog.hide()

    def _toggle_owned_dialog(self, dialog) -> bool:
        """Show child dialogs above the main UI; return True only when caller should hide."""
        if dialog.isVisible() and dialog.isActiveWindow():
            return True
        self._show_owned_dialog(dialog)
        return False

    def _show_owned_dialog(self, dialog) -> None:
        if dialog is None:
            return
        if dialog.windowState() & Qt.WindowMinimized:
            dialog.setWindowState(dialog.windowState() & ~Qt.WindowMinimized)
        if self.main_window and not dialog.isVisible():
            base = self.main_window.frameGeometry()
            dialog.move(base.x() + 80, base.y() + 80)
        dialog.show()
        dialog.setWindowState(dialog.windowState() & ~Qt.WindowMinimized)
        dialog.raise_()
        dialog.activateWindow()
        QApplication.setActiveWindow(dialog)

    def _set_map_click_mode(self, mode: str):
        self.map_click_mode = mode
        if mode != "SET_EXIT":
            self.btn_set_exit.setChecked(False)
        if mode != "ADD_REQUIRED_POINT":
            self.btn_add_required.setChecked(False)
        if mode != "ADD_GUIDE_POINT":
            self.btn_add_guide.setChecked(False)

    def toggle_exit_mode(self):
        if not self.map_folder_path:
            self.btn_set_exit.setChecked(False)
            return
        mode = "SET_EXIT" if self.btn_set_exit.isChecked() else "NONE"
        self._set_map_click_mode(mode)
        if mode == "SET_EXIT":
            self.status_label.setText("请在地图上点击出口位置")

    def toggle_guide_mode(self):
        if not self.map_folder_path:
            self.btn_add_guide.setChecked(False)
            return
        mode = "ADD_GUIDE_POINT" if self.btn_add_guide.isChecked() else "NONE"
        self._set_map_click_mode(mode)
        if mode == "ADD_GUIDE_POINT":
            self.status_label.setText("请在地图上点击A*辅助点；顺序仅用于撤销")

    def toggle_required_mode(self):
        if not self.map_folder_path:
            self.btn_add_required.setChecked(False)
            return
        mode = "ADD_REQUIRED_POINT" if self.btn_add_required.isChecked() else "NONE"
        self._set_map_click_mode(mode)
        if mode == "ADD_REQUIRED_POINT":
            self.status_label.setText("请在地图上依次点击必经点")

    def _set_route_buttons_enabled(self, enabled: bool):
        self.btn_set_exit.setEnabled(enabled)
        self.btn_add_required.setEnabled(enabled)
        self.btn_undo_required.setEnabled(enabled)
        self.btn_add_guide.setEnabled(enabled)
        self.btn_undo_guide.setEnabled(enabled)
        self.btn_clear_route.setEnabled(enabled)
        self.btn_save_route.setEnabled(enabled)
        self.btn_auto_nav.setEnabled(enabled)

    def load_route_data(self):
        if not self.map_folder_path:
            self.route_data = None
            self.navigation_task_controller.load_route(None)
            return None
        self.route_data = self.route_manager.load_route(self.map_folder_path, force_reload=True)
        main_route = (self.route_data or {}).get("routes", {}).get("main", {})
        self.navigation_task_controller.load_route(main_route)
        return self.route_data

    def save_route(self):
        if not self.map_folder_path:
            return
        if self.route_manager.save_route(self.map_folder_path):
            self.load_route_data()
            self._render_route_overlay()
            self.status_label.setText("路线已保存")
        else:
            QMessageBox.warning(self, "警告", "保存路线失败")

    def undo_guide_point(self):
        if not self.map_folder_path:
            return
        self.route_manager.undo_guide_point(self.map_folder_path)
        self.route_data = self.route_manager.load_route(self.map_folder_path)
        self._render_route_overlay()
        self.status_label.setText("已撤销最后一个途经点")

    def undo_required_point(self):
        if not self.map_folder_path:
            return
        self.route_manager.undo_required_point(self.map_folder_path)
        self.route_data = self.route_manager.load_route(self.map_folder_path)
        self._render_route_overlay()
        self.status_label.setText("已撤销最后一个必经点")

    def clear_route(self):
        if not self.map_folder_path:
            return
        self.route_manager.clear_route(self.map_folder_path)
        self.route_data = self.route_manager.load_route(self.map_folder_path)
        self._render_route_overlay()
        self.status_label.setText("路线已清空")

    def _clear_route_overlay(self):
        self.route_overlay_items, self.route_path_item = clear_route_overlay(
            self.scene,
            self.route_overlay_items,
        )

    def _clear_event_overlay(self):
        self.event_overlay_items = clear_event_overlay(
            self.scene,
            self.event_overlay_items,
        )

    def _global_to_scene(self, point):
        return global_to_scene(point, self.nav_core)

    def _render_event_overlay(self):
        self.event_overlay_items = render_event_overlay(
            self.scene,
            self.nav_core,
            self.event_coordinator,
            self.event_overlay_items,
        )

    def _render_route_overlay(
        self,
        current_path=None,
        current_subgoal=None,
        current_required_index=None,
        current_guide_index=None,
        current_target_kind=None,
    ):
        if not self.scene or not self.nav_core:
            return

        self.route_overlay_items, self.route_path_item = render_route_overlay(
            self.scene,
            self.nav_core,
            self.route_data,
            self.route_overlay_items,
            current_path=current_path,
            current_subgoal=current_subgoal,
            current_required_index=current_required_index,
            current_guide_index=current_guide_index,
            current_target_kind=current_target_kind,
        )
        self._render_event_overlay()

    def _can_start_auto_navigation(self):
        if not self.map_folder_path or not self.nav_core:
            return False, "请先加载地图"
        main = (self.route_data or {}).get("routes", {}).get("main", {})
        if not main.get("exit_region"):
            return False, "请先设置出口"
        if not self.nav_config.game_screen_center:
            return False, "请先校准屏幕中心"
        if (not self.nav_config.monitor_logical_center and not self.nav_config.monitor_region) or not self.nav_config.monitor_size:
            return False, "缺少监视窗口配置"
        return True, ""

    def _set_game_input_window_mode(self, enabled: bool):
        """Keep the tool window from covering the game while auto navigation clicks."""
        if not self.main_window:
            return

        if enabled:
            if not self._game_input_window_mode:
                self._main_window_was_topmost = bool(
                    self.main_window.windowFlags() & Qt.WindowStaysOnTopHint
                )
                if self._main_window_was_topmost:
                    self.main_window.setWindowFlag(Qt.WindowStaysOnTopHint, False)
                    self.main_window.show()
                self._game_input_window_mode = True
                print("DEBUG: Game input mode enabled; main window is no longer topmost.")
            self.main_window.lower()
            return

        if not self._game_input_window_mode:
            return
        if self._main_window_was_topmost:
            self.main_window.setWindowFlag(Qt.WindowStaysOnTopHint, True)
            self.main_window.show()
        self._game_input_window_mode = False
        print("DEBUG: Game input mode disabled; main window topmost state restored.")

    def toggle_auto_navigation(self):
        if self.btn_auto_nav.isChecked():
            ok, message = self._can_start_auto_navigation()
            if not ok:
                self.btn_auto_nav.setChecked(False)
                QMessageBox.warning(self, "警告", message)
                return
            main_route = (self.route_data or {}).get("routes", {}).get("main", {})
            self.navigation_task_controller.load_route(main_route)
            if not self.navigation_task_controller.start():
                self.btn_auto_nav.setChecked(False)
                QMessageBox.warning(self, "警告", "路线数据无效，无法启动自动导航")
                return
            if not self.nav_timer.isActive():
                self.btn_start.setChecked(True)
                self.toggle_navigation()
                if not self.nav_timer.isActive():
                    self.navigation_task_controller.stop()
                    self.auto_navigation_enabled = False
                    self.btn_auto_nav.setChecked(False)
                    return
            self.auto_navigation_enabled = True
            self._set_game_input_window_mode(True)
            self.status_label.setText("自动导航已启动，等待稳定定位")
        else:
            self.auto_navigation_enabled = False
            self.navigation_task_controller.stop()
            self._set_game_input_window_mode(False)
            self._render_route_overlay()
            self.status_label.setText("自动导航已停止")

    def refresh_map_list(self):
        """
        刷新地图选择下拉框的内容

        扫描项目根目录下的 map_data 文件夹，获取所有子目录名称（每个子目录代表一个地图），
        并将其添加到地图选择下拉框中。如果 map_data 文件夹不存在，则显示提示信息。

        地图目录结构:
            map_data/
            ├── 地图名称 1/
            │   ├── config.json
            │   └── ...
            ├── 地图名称 2/
            └── ...

        返回:
            无

        异常:
            无直接异常，文件夹不存在时会在下拉框中显示提示信息
        """
        self.map_combo.clear()  # 清空下拉框现有内容

        dirs = list_map_names(__file__)
        if dirs:
            self.map_combo.addItems(dirs)  # 将所有地图名称添加到下拉框
        else:
            # map_data 文件夹不存在，显示提示信息
            self.map_combo.addItem(MISSING_MAP_DATA_LABEL)

    def load_map(self):
        """
        加载用户选中的地图

        执行步骤:
        1. 从下拉框获取选中的地图名称
        2. 构建地图文件夹路径
        3. 读取或创建配置文件 (config.json)
        4. 初始化导航核心引擎 (NavigationCore)
        5. 应用配置参数到核心模块
        6. 渲染地图到图形视图
        7. 启用相关功能按钮

        返回:
            无

        异常:
            Exception: 加载过程中任何错误都会弹出错误对话框，包含具体错误信息
        """
        # 获取用户选中的地图名称
        map_name = self.map_combo.currentText()
        if not map_name or map_name == MISSING_MAP_DATA_LABEL:
            # 没有有效地图选中，直接返回
            return

        # 构建地图文件夹的绝对路径
        self.map_folder_path = resolve_map_folder(__file__, map_name)

        try:
            # 尝试读取地图配置文件
            self.nav_config, config_exists = load_nav_config(self.map_folder_path)
            if not config_exists:
                # 配置文件不存在，使用默认配置并提示用户
                QMessageBox.warning(self, "警告", "未找到 config.json，将使用默认参数。")

            # 初始化导航核心引擎，加载地图图像和特征
            self.nav_core = NavigationCore(self.map_folder_path)
            self._apply_config_to_core()  # 将配置参数应用到核心模块

            # 计算物理坐标并缓存（避免 navigation_loop 重复计算）
            self._capture_center_physical = None
            physical_center = (0, 0)
            if self.nav_config.monitor_logical_center:
                sx, sy = self._compute_scale()
                self._capture_center_physical = physical_center_from_logical(
                    self.nav_config.monitor_logical_center,
                    (sx, sy),
                )
                physical_center = self._capture_center_physical
                print(f"地图 '{map_name}' 加载完成，物理坐标：{self._capture_center_physical}")

            # 实时计算物理坐标以更新 UI
            self.params_dialog.set_config_to_ui(self.nav_config, physical_center)
            self.load_route_data()
            self._initialize_event_system()

            self._render_map()  # 渲染地图到图形视图

            # 显示上次退出的位置（从 npz 文件的 current_pos 加载）
            self._show_last_exit_position()
            self._render_route_overlay()

            # 启用功能按钮
            self.btn_start.setEnabled(True)  # 启用开始导航按钮
            self.btn_hint.setEnabled(True)  # 启用设置初始位置按钮
            self._set_route_buttons_enabled(True)
            self.status_label.setText(f"地图 '{map_name}' 加载成功。请设置初始位置或直接开始导航。")

        except Exception as e:
            # 捕获任何异常并显示错误对话框
            QMessageBox.critical(self, "错误", f"加载地图失败：{str(e)}")

    def _initialize_event_system(self):
        if not self.map_folder_path:
            self.event_config = None
            self.event_coordinator = None
            return
        self.event_config = load_event_config(self.map_folder_path)
        self.event_coordinator = EventCoordinator(self.event_registry, self.event_config)
        self.event_capture_provider = GameWindowCaptureProvider(
            self.app_context.screen_capture,
            window_finder=self._find_game_window_rect,
        )
        self._refresh_event_dialog()
        event_log(
            "event system initialized",
            map=self.map_combo.currentText() if self.map_combo else "",
            enabled=bool(getattr(self.event_config, "enabled", True)),
            events=event_config_summary(self.event_config),
        )

    def _refresh_event_dialog(self):
        if not self.event_dialog:
            return
        self.event_dialog.set_context(
            self.event_registry,
            self.event_config,
            self.event_coordinator,
            self.map_combo.currentText() if self.map_combo else "",
        )

    def _on_event_config_changed(self, event_config):
        self.event_config = event_config
        if self.event_coordinator:
            self.event_coordinator.config = event_config
        self._clear_event_overlay()
        event_log(
            "event config changed",
            enabled=bool(getattr(event_config, "enabled", True)),
            events=event_config_summary(event_config),
        )

    def _save_event_config(self):
        if not self.map_folder_path or not self.event_config:
            QMessageBox.warning(self, "事件管理", "未加载地图或事件配置。")
            return
        if save_event_config(self.map_folder_path, self.event_config):
            self._refresh_event_dialog()
            QMessageBox.information(self, "事件管理", "事件配置已保存。")
        else:
            QMessageBox.critical(self, "事件管理", "保存 event_config.json 失败。")

    def _reset_portal_event_state(self):
        if not self.event_coordinator:
            QMessageBox.warning(self, "事件管理", "请先加载地图并初始化事件系统。")
            return
        if self.portal_test_controller.active:
            self._set_portal_manual_test_active(False, reason="portal state reset")
        removed = self.event_coordinator.reset_event_type("portal", now_ms=int(time.time() * 1000))
        self._reset_event_move_runtime()
        self._clear_event_overlay()
        self._render_event_overlay()
        if self.event_dialog:
            self.event_dialog.refresh_tasks()
        event_log("portal event state reset", removed=removed)
        self.status_label.setText(f"传送门状态已刷新，清理 {removed} 个任务；可重新识别测试")

    def _find_game_window_rect(self):
        return find_default_game_window_rect()

    def _build_event_tick(self, now_ms, frame, player_pos, localized_pos, conf):
        return build_event_tick(
            now_ms=now_ms,
            frame=frame,
            player_pos=player_pos,
            localized_pos=localized_pos,
            confidence=conf,
            nav_core=self.nav_core,
            nav_config=self.nav_config,
            map_name=self.map_combo.currentText() if self.map_combo else "",
            capture_provider=self.event_capture_provider,
        )

    def _reset_event_move_runtime(self):
        self.navigation_task_controller.movement.reset()
        self.navigation_task_controller.event_approach.reset()

    def _run_portal_manual_test(self):
        if self.portal_test_controller.active:
            self._set_portal_manual_test_active(False, reason="button stop")
            return

        if not self.event_coordinator or not self.nav_core:
            self.portal_test_controller.reset_button()
            QMessageBox.warning(self, "事件管理", "请先加载地图并初始化事件系统。")
            return
        if not self.nav_config.game_screen_center:
            self.portal_test_controller.reset_button()
            QMessageBox.warning(self, "事件管理", "请先校准屏幕中心。")
            return
        if not self.nav_timer.isActive():
            self.btn_start.setChecked(True)
            self.toggle_navigation()
            if not self.nav_timer.isActive():
                self.portal_test_controller.reset_button()
                return

        self._set_portal_manual_test_active(True, reason="button start")

    def _set_portal_manual_test_active(self, active: bool, reason: str = "") -> None:
        if active:
            start_event_log_session("portal_manual_test")
            main_route = (self.route_data or {}).get("routes", {}).get("main", {})
            self.navigation_task_controller.load_route(main_route)
            self.navigation_task_controller.start()
            self.portal_test_controller.start()
            self._set_game_input_window_mode(True)
            self.motion_controller.set_control_enabled(True)
            event_log("portal manual event test started", reason=reason)
            self.status_label.setText("传送门测试已启动：使用正式事件流程执行")
            return

        self.portal_test_controller.stop()
        self._reset_event_move_runtime()
        if not self.auto_navigation_enabled:
            self._set_game_input_window_mode(False)
        event_log("portal manual event test stopped", reason=reason)
        self.status_label.setText("传送门测试已停止")

    def _render_map(self):
        """
        渲染地图图像和所有图形标记到视图中。

        执行步骤:
        1. 从导航核心获取拼接后的完整地图图像。
        2. 将OpenCV图像(BGR)转换为Qt图像(RGB)。
        3. 清空并重新构建场景：
           - 添加地图背景 (map_item)。
           - 创建玩家位置标记 (player_item, 红色圆点)。
           - 创建目标位置标记 (target_item, 绿色十字)。
           - 创建监控区域矩形框 (monitor_rect_item, 绿色虚线框)。
        4. 调整视图以适应地图大小。
        """
        map_img = self.nav_core.get_map_image()
        h, w, c = map_img.shape

        if not map_img.flags['C_CONTIGUOUS']:
            map_img = np.ascontiguousarray(map_img)

        qimg = QImage(map_img.data, w, h, w * c, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)

        # --- 场景重建 ---
        self.scene.clear()
        self.route_overlay_items = []
        self.event_overlay_items = []
        self.route_path_item = None

        # 1. 添加地图背景
        self.map_item = self.scene.addPixmap(pixmap)
        self.map_item.setZValue(0)

        # 2. 重置独立管理的标记项
        self.last_pos_item = None
        self.hint_item = None

        # 3. 创建玩家位置标记 (红色圆点)
        red_color = QColor("red")
        self.player_item = self.scene.addEllipse(-5, -5, 10, 10, QPen(red_color), QBrush(red_color))
        self.player_item.setZValue(4)
        self.player_item.setVisible(False)

        # 4. 创建目标位置标记 (绿色十字) - 修复 AttributeError
        target_pen = QPen(QColor(0, 255, 0, 200), 2)
        path = QPainterPath()
        path.moveTo(-10, 0)
        path.lineTo(10, 0)
        path.moveTo(0, -10)
        path.lineTo(0, 10)
        self.target_item = self.scene.addPath(path, target_pen)
        self.target_item.setZValue(5)
        self.target_item.setVisible(False)

        # 5. 创建监控区域矩形框 (绿色虚线框) - 恢复绿框显示
        green_pen = QPen(QColor(0, 255, 0, 150), 2, Qt.DashLine)
        self.monitor_rect_item = self.scene.addRect(0, 0, 0, 0, green_pen)
        self.monitor_rect_item.setZValue(2)
        self.monitor_rect_item.setVisible(False) # 初始隐藏，待更新位置后显示

        orange_pen = QPen(QColor(255, 140, 0, 190), 2, Qt.DashLine)
        self.game_view_rect_item = self.scene.addRect(0, 0, 0, 0, orange_pen)
        self.game_view_rect_item.setZValue(2)
        self.game_view_rect_item.setVisible(False)

        # 调整视图
        self.view.fitInView(self.map_item, Qt.KeepAspectRatio)

    def _build_capture_geometry(self):
        """根据当前配置返回真实截图矩形和玩家在截图中的相对位置。"""
        if not self.nav_config:
            return None, None

        if self._capture_center_physical is None and self.nav_config.monitor_logical_center:
            sx, sy = self._compute_scale()
            self._capture_center_physical = physical_center_from_logical(
                self.nav_config.monitor_logical_center,
                (sx, sy),
            )
        rect, player_pos, self._capture_center_physical = build_capture_geometry(
            self.nav_config,
            self._capture_center_physical,
        )
        return rect, player_pos

    def _update_overlay_display(self):
        """根据当前配置实时更新屏幕幕布显示。"""
        if not self.params_dialog.nav_toggle_overlay_btn.isChecked():
            return

        capture_rect, _ = self._build_capture_geometry()
        if not capture_rect:
            self.overlay.hide_overlay()
            return

        rect, anchor = screen_overlay_geometry(
            capture_rect,
            self.nav_config,
            self._compute_scale(),
        )
        if not rect:
            self.overlay.hide_overlay()
            return
        self.overlay.set_rect_and_show(
            rect["left"],
            rect["top"],
            rect["width"],
            rect["height"],
            anchor=anchor,
        )

    def _update_monitor_rect(self, player_pos, capture_rect=None, player_local_pos=None):
        """
        根据传入的玩家位置和配置更新监控区域矩形框（绿框）。

        该方法从导航核心和配置中获取必要参数，计算绿框在场景中的
        正确位置和大小，并更新其可见性。
        """
        if not all([self.monitor_rect_item, player_pos, self.nav_core, self.nav_config]):
            return

        capture_rect = capture_rect or self._current_capture_rect
        player_local_pos = player_local_pos or self._current_player_local_pos
        rect = monitor_scene_rect(player_pos, capture_rect, player_local_pos, self.nav_core)
        if not rect:
            return

        self.monitor_rect_item.setRect(*rect)
        if not self.monitor_rect_item.isVisible():
            self.monitor_rect_item.setVisible(True)

    def _update_game_view_rect(self, player_pos):
        """Update the orange real-game-view rectangle in map coordinates."""
        if not all([self.game_view_rect_item, player_pos, self.nav_core, self.nav_config]):
            return

        rect = game_view_scene_rect(player_pos, self.nav_core, self.nav_config)
        if not rect:
            self.game_view_rect_item.setVisible(False)
            return

        self.game_view_rect_item.setRect(*rect)
        if not self.game_view_rect_item.isVisible():
            self.game_view_rect_item.setVisible(True)

    def _refresh_game_view_rect_from_known_position(self):
        """Refresh the orange rectangle immediately after display-related params change."""
        if not self.nav_core:
            return

        player_pos = (
            self.nav_core.current_pos
            or self.nav_core.last_good_pos
            or self.nav_core.drawing_saved_pos
        )
        if player_pos:
            self._update_game_view_rect(player_pos)

    def _show_last_exit_position(self):
        """
        显示上次退出时的位置（从 npz 文件的 current_pos 加载）

        该位置是绘图模式保存的最后位置，用紫色圆点表示。
        这个标记独立于用户点击的初始位置和实时定位的玩家位置。

        返回:
            无

        异常:
            无直接异常
        """
        if not self.nav_core or not self.nav_core.drawing_saved_pos:
            print("没有上次退出的位置信息")
            return

        # 获取上次退出的全局坐标
        last_pos_global = self.nav_core.drawing_saved_pos
        print(f"=== 加载地图：显示上次退出位置 (绘图模式保存) ===")
        print(f"  1. 上次退出位置 (绘图模式): ({last_pos_global[0]:.2f}, {last_pos_global[1]:.2f})")

        # 获取地图裁剪偏移量，将全局坐标转换为显示坐标
        offset_x, offset_y = self.nav_core.crop_offset
        display_x = last_pos_global[0] - offset_x
        display_y = last_pos_global[1] - offset_y

        # 创建或获取上次退出位置标记项（紫色圆点）
        if not self.last_pos_item:
            purple_color = QColor(128, 0, 128)  # 紫色
            self.last_pos_item = self.scene.addEllipse(-5, -5, 10, 10, QPen(purple_color), QBrush(purple_color))
            self.last_pos_item.setZValue(3)  # 设置最高层级，确保在其他标记之上

        # 设置位置并显示
        self.last_pos_item.setPos(display_x, display_y)
        self.last_pos_item.setVisible(True)

    def _apply_config_to_core(self):
        """
        将当前的导航配置 (nav_config) 应用到所有核心模块

        应用范围:
        1. 识别器 (Recognizer): 更新识别参数和绘制缩放系数
        2. 运动控制器 (MotionController): 更新屏幕中心坐标和移动缩放系数
        3. 更新地图裁剪偏移量 (crop_offset)

        注意:
        - 此方法在加载地图、保存配置、开始导航时调用
        - 确保核心模块使用最新的配置参数

        返回:
            无

        异常:
            无直接异常，如果 nav_core 或 nav_config 为空则静默返回
        """
        # 检查导航核心和配置是否已初始化
        if not self.nav_core or not self.nav_config:
            return

        # 1. 应用参数到识别器
        # 将 NavConfig 中的 recognizer_params 转换为字典传递给识别器
        rec_params_dict = self.nav_config.recognizer_params.__dict__
        self.nav_core.recognizer.set_params(rec_params_dict)  # 设置识别器参数
        map_draw_scale = float(getattr(self.nav_core, "map_draw_scale", self.nav_core.draw_scale))
        if abs(float(self.nav_config.draw_scale) - map_draw_scale) > 0.001:
            event_log(
                "navigation draw_scale config mismatch",
                config_draw_scale=float(self.nav_config.draw_scale),
                map_draw_scale=map_draw_scale,
                action="use_map_npz_draw_scale",
            )
            self.nav_config.draw_scale = map_draw_scale
        self.nav_core.draw_scale = map_draw_scale  # map_data.npz 是定位缩放的唯一可信来源
        self.nav_core.wall_match_close_kernel_size = max(
            1,
            int(getattr(self.nav_core, "map_wall_match_close_kernel_size", getattr(self.nav_config, "wall_match_close_kernel_size", 3))),
        )
        self.nav_core.rebuild_navigation_wall_layer(
            erode_iterations=self.nav_config.nav_wall_erode_iterations,
        )
        self.nav_core.last_player_local_pos = None
        self.app_context.path_finder.start_clear_radius = max(0, int(self.nav_config.path_start_clear_radius))
        self.app_context.path_finder.walkable_snap_radius = max(0, int(self.nav_config.path_walkable_snap_radius))
        event_log(
            "navigation obstacle config applied",
            nav_wall_erode_iterations=self.nav_config.nav_wall_erode_iterations,
            path_start_clear_radius=self.app_context.path_finder.start_clear_radius,
            path_walkable_snap_radius=self.app_context.path_finder.walkable_snap_radius,
            draw_scale=self.nav_core.draw_scale,
            wall_match_close_kernel_size=self.nav_core.wall_match_close_kernel_size,
        )
        self._capture_center_physical = None

        # 2. 更新地图裁剪偏移量
        # 调用 get_map_image() 会重新计算 crop_offset
        # 这确保了在 draw_scale 改变后，显示坐标仍然正确
        self.nav_core.get_map_image()

        # 3. 更新运动控制器参数
        # 只有在配置了屏幕中心坐标时才更新运动控制器
        if self.nav_config.game_screen_center:
            self.motion_controller.set_params(
                game_screen_center=self.nav_config.game_screen_center,  # 游戏屏幕中心坐标（物理像素）
                movement_scale_factor=self.nav_config.movement_scale_factor,  # 移动缩放系数，用于调整移动距离
                movement_min_click_radius=self.nav_config.movement_min_click_radius,
                movement_max_click_radius=self.nav_config.movement_max_click_radius,
                bottom_click_guard_pixels=self.nav_config.bottom_click_guard_pixels,
            )
        self._configure_navigation_task_controller()

    def _on_parameter_changed(self, new_config: NavConfig):
        """
        当参数对话框中的参数发生变化时调用

        此方法仅更新配置对象，不立即应用到核心模块。
        用户需要点击"保存"按钮才会真正应用新参数。

        参数:
            new_config (NavConfig): 从参数对话框传来的新配置对象，
                                   包含用户修改后的所有导航参数

        返回:
            无

        异常:
            无直接异常
        """
        # 检查导航核心是否已初始化
        if not self.nav_core:
            return

        # 更新为从 UI 传来的新配置
        self.nav_config = new_config
        self._capture_center_physical = None
        self._update_overlay_display()
        if self.nav_config.game_screen_center:
            self.motion_controller.set_params(
                game_screen_center=self.nav_config.game_screen_center,
                movement_scale_factor=self.nav_config.movement_scale_factor,
                movement_min_click_radius=self.nav_config.movement_min_click_radius,
                movement_max_click_radius=self.nav_config.movement_max_click_radius,
                bottom_click_guard_pixels=self.nav_config.bottom_click_guard_pixels,
            )
        self._configure_navigation_task_controller()
        self._refresh_game_view_rect_from_known_position()

        # 更新参数对话框的状态标签，提示用户有未保存的修改
        self.params_dialog.nav_status_label.setText("有未保存的修改")

    def _configure_navigation_task_controller(self):
        if self.nav_core and self.nav_config:
            self.nav_core.visual_check_interval_ms = max(0, int(self.nav_config.coordinate_visual_check_interval_ms))
            self.nav_core.visual_check_margin = max(0, int(self.nav_config.coordinate_visual_check_margin))
            self.nav_core.visual_check_min_confidence = max(
                0.0,
                min(0.99, float(self.nav_config.coordinate_visual_match_min_confidence)),
            )
            self.nav_core.visual_mismatch_threshold = max(0.0, float(self.nav_config.coordinate_visual_mismatch_threshold))

        diagnostics = self.navigation_task_controller.coordinate_diagnostics
        diagnostics.visual_mismatch_threshold = max(0.0, float(self.nav_config.coordinate_visual_mismatch_threshold))
        diagnostics.visual_mismatch_required_frames = max(1, int(self.nav_config.coordinate_visual_mismatch_frames))

        movement = self.navigation_task_controller.movement
        movement.click_cooldown_ms = max(120, int(self.nav_config.auto_click_cooldown_ms))
        movement.min_click_target_delta = max(0.0, float(self.nav_config.auto_min_click_target_delta))
        movement.anchor_arrival_radius = max(4.0, float(self.nav_config.anchor_arrival_radius))
        movement.progress_timeout_ms = max(200, int(self.nav_config.movement_progress_timeout_ms))
        movement.min_progress_delta = max(0.0, float(self.nav_config.movement_min_progress_delta))
        movement.max_recover_attempts = max(0, int(self.nav_config.movement_max_recover_attempts))
        movement.path_deviation_threshold = max(8.0, float(self.nav_config.movement_path_deviation_threshold))
        self.navigation_task_controller.event_approach.configure(
            enabled=bool(self.nav_config.event_approach_enabled),
            game_view_map_size=max(100, int(self.nav_config.game_view_map_size)),
            visible_margin=max(0, int(self.nav_config.event_visible_margin)),
            approach_lookahead=max(8.0, float(self.nav_config.event_approach_lookahead)),
            click_cooldown_ms=max(120, int(self.nav_config.event_approach_click_cooldown_ms)),
            stop_radius=max(4.0, float(self.nav_config.event_stop_radius)),
            settle_ms=max(0, int(self.nav_config.event_settle_ms)),
            stable_frames=max(1, int(self.nav_config.event_stable_frames)),
            max_motion_per_frame=max(0.0, float(self.nav_config.event_max_motion_per_frame)),
        )

    def _save_nav_config(self):
        """
        保存当前导航配置到地图文件夹的 config.json 文件

        执行步骤:
        1. 检查是否已加载地图（有 map_folder_path）
        2. 将配置序列化为字典并写入 JSON 文件
        3. 应用配置到核心模块
        4. 更新 UI 状态提示

        返回:
            无

        异常:
            Exception: 写入文件失败时弹出错误对话框，包含具体错误信息
        """
        # 检查是否已加载地图
        if not self.map_folder_path:
            QMessageBox.warning(self, "错误", "没有加载地图，无法保存参数。")
            return

        try:
            # 1. 将当前配置写入文件
            # 使用 indent=4 格式化输出，ensure_ascii=False 支持中文
            save_nav_config(self.map_folder_path, self.nav_config)

            # 2. 将这套完整的配置应用到核心模块
            self._apply_config_to_core()
            self._update_overlay_display()
            self._refresh_game_view_rect_from_known_position()

            # 3. 更新 UI 状态
            self.params_dialog.nav_status_label.setText("参数已保存并应用")
            QMessageBox.information(self, "成功", "参数已保存并成功应用到当前导航。")

        except Exception as e:
            # 捕获写入异常并显示错误对话框
            QMessageBox.critical(self, "保存失败", f"无法写入 config.json: {e}")
            self.params_dialog.nav_status_label.setText("保存失败!")

    def _save_nav_default_config(self):
        if not self.nav_config:
            QMessageBox.warning(self, "错误", "没有可保存的导航参数。")
            return
        try:
            path = save_default_nav_config(__file__, self.nav_config)
            self.params_dialog.nav_status_label.setText("已保存为默认配置")
            QMessageBox.information(self, "成功", f"默认导航配置已保存到：{path}")
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"无法写入默认 config.json: {e}")
            self.params_dialog.nav_status_label.setText("默认配置保存失败!")

    def _compute_scale(self):
        """
        计算从 Qt 逻辑坐标到物理像素的缩放系数

        Qt 使用逻辑像素（考虑高 DPI 缩放），而屏幕截图使用物理像素。
        此方法获取主屏幕的设备像素比 (DPR)，用于两种坐标系统之间的转换。

        坐标系统说明:
        - 逻辑坐标：Qt 使用的坐标系统，考虑了系统 DPI 缩放
        - 物理坐标：屏幕实际像素坐标，用于屏幕截图

        返回:
            tuple: (scale_x, scale_y) 缩放系数元组
                - scale_x (float): X 方向缩放系数
                - scale_y (float): Y 方向缩放系数
                通常两个值相等，等于屏幕的设备像素比 (DPR)

        异常:
            无直接异常，如果 DPR 获取失败则返回 (1.0, 1.0) 作为兜底值
        """
        # 获取主屏幕对象
        screen = QApplication.primaryScreen()
        # 获取设备像素比 (Device Pixel Ratio)
        # 例如：DPR=2 表示 1 个逻辑像素对应 2x2 个物理像素
        dpr = screen.devicePixelRatio()

        if dpr > 0:
            # DPR 有效，返回缩放系数
            return dpr, dpr
        return 1.0, 1.0  # 兜底值，防止除以零错误

    def _toggle_overlay_display(self):
        """
        切换调试幕布的显示/隐藏状态

        调试幕布用于可视化显示屏幕截图的监控区域，
        帮助开发者确认截图位置是否正确。

        执行步骤:
        1. 检查配置是否有效（有监控中心坐标）
        2. 根据按钮状态切换幕布显示/隐藏
        3. 显示时使用逻辑坐标，幕布组件内部会处理坐标转换

        返回:
            无

        异常:
            无直接异常，配置无效时弹出警告对话框
        """
        # 检查配置是否有效
        if not self.nav_config or (not self.nav_config.monitor_logical_center and not self.nav_config.monitor_region):
            # 配置无效，重置按钮状态并提示用户
            self.params_dialog.nav_toggle_overlay_btn.setChecked(False)
            QMessageBox.warning(self, "警告", "地图配置不完整，无法显示幕布。")
            return

        # 切换显示状态
        if self.params_dialog.nav_toggle_overlay_btn.isChecked():
            self._update_overlay_display()
        else:
            # 按钮未选中，隐藏幕布
            self.overlay.hide_overlay()

    def eventFilter(self, watched, event):
        """
        事件过滤器，用于捕获图形场景中的鼠标点击事件

        此方法拦截发送到 scene 的事件，特别处理鼠标左键点击事件，
        将其转发到 handle_map_click 方法进行处理。

        参数:
            watched (QObject): 被监视的对象，此处为 QGraphicsScene
            event (QEvent): 事件对象，包含事件类型和相关信息

        返回:
            bool: 是否处理了该事件
                - True: 事件已处理，阻止进一步传播
                - False: 事件未处理，继续传递给父类

        异常:
            无直接异常
        """
        # 检查是否是场景的鼠标左键按下事件
        if watched == self.scene and event.type() == QEvent.GraphicsSceneMousePress and event.button() == Qt.LeftButton:
            # 是鼠标左键点击，转发到 handle_map_click 处理
            self.handle_map_click(event.scenePos())  # 获取点击的场景坐标并处理
            return True  # 事件已处理，阻止进一步传播
        return super().eventFilter(watched, event)  # 其他事件交给父类处理

    def handle_map_click(self, pos):
        """Handle map clicks for hint placement, route editing, or manual movement."""
        if not self.nav_core:
            return

        offset_x, offset_y = self.nav_core.crop_offset
        global_point = (int(pos.x() + offset_x), int(pos.y() + offset_y))

        if self.btn_hint.isChecked():
            self.set_initial_hint(pos)
            return

        if self.map_click_mode == "SET_EXIT":
            self.route_manager.set_exit_region(self.map_folder_path, global_point, radius=28)
            self.route_data = self.route_manager.load_route(self.map_folder_path)
            self._render_route_overlay()
            self._set_map_click_mode("NONE")
            self.status_label.setText(f"出口已设置: ({global_point[0]}, {global_point[1]})")
            return

        if self.map_click_mode == "ADD_REQUIRED_POINT":
            self.route_manager.add_required_point(self.map_folder_path, global_point)
            self.route_data = self.route_manager.load_route(self.map_folder_path)
            self._render_route_overlay()
            self.status_label.setText(f"已添加必经点: ({global_point[0]}, {global_point[1]})")
            return

        if self.map_click_mode == "ADD_GUIDE_POINT":
            self.route_manager.add_guide_point(self.map_folder_path, global_point)
            self.route_data = self.route_manager.load_route(self.map_folder_path)
            self._render_route_overlay()
            self.status_label.setText(f"已添加途经点: ({global_point[0]}, {global_point[1]})")
            return

        if not self.nav_core.is_localized or not self.nav_core.current_pos:
            QMessageBox.warning(self, "警告", "请先完成定位后再点击移动目标。")
            return

        target_global_pos = (float(global_point[0]), float(global_point[1]))
        player_global_pos = self.nav_core.current_pos
        self.motion_controller.move_to_map_target(player_global_pos, target_global_pos)

        self.target_item.setPos(pos)
        self.target_item.setVisible(True)
        self.status_label.setText(f"移动目标: ({pos.x():.1f}, {pos.y():.1f})")

    def set_initial_hint(self, scene_pos):
        """
        处理用户在地图上点击设置初始位置的逻辑。

        1. 在场景中创建一个蓝色圆点 (hint_item) 以标记用户点击的位置。
        2. 调用导航核心 (nav_core) 的 set_initial_hint 方法，
           将点击的场景坐标转换为全局坐标后传递给核心模块。
        3. 更新状态栏信息，提示用户等待定位校准。
        4. 取消"设置初始位置"按钮的选中状态并恢复UI。
        """
        # 1. 修正坐标：将显示坐标转换为全局坐标
        offset_x, offset_y = self.nav_core.crop_offset
        global_x = scene_pos.x() + offset_x
        global_y = scene_pos.y() + offset_y

        # 2. 将初始位置提示传递给导航核心
        self.nav_core.set_initial_hint((global_x, global_y))

        # 3. 在UI上标记用户点击的位置 (蓝色圆点)
        if not self.hint_item:
            blue_color = QColor("blue")
            self.hint_item = self.scene.addEllipse(-5, -5, 10, 10, QPen(blue_color), QBrush(blue_color))
            self.hint_item.setZValue(3)
        self.hint_item.setPos(scene_pos)
        self.hint_item.setVisible(True)

        # 4. 在设置初始提示时，也更新监控框的位置，提供即时反馈
        self._update_monitor_rect((global_x, global_y))
        self._update_game_view_rect((global_x, global_y))

        # 5. 打印调试信息
        print(f"=== 设置初始位置提示 (用户点击) ===")
        print(f"  - 点击的显示坐标: ({scene_pos.x():.2f}, {scene_pos.y():.2f})")
        print(f"  - 地图裁剪偏移量: ({offset_x:.2f}, {offset_y:.2f})")
        print(f"  - 转换后的全局坐标: ({global_x:.2f}, {global_y:.2f})")

        # 6. 更新状态栏
        self.status_label.setText(f"初始位置提示已设置：({int(global_x)}, {int(global_y)})。")

        # 7. 重置提示按钮状态并恢复UI
        self.btn_hint.setChecked(False)
        self.toggle_hint_mode()

    def toggle_hint_mode(self):
        """
        切换提示模式的 UI 状态

        当用户点击"设置初始位置"按钮时，切换视图的拖拽模式和光标样式:
        - 提示模式激活：禁用拖拽，显示十字光标
        - 提示模式取消：启用手形拖拽，显示箭头光标

        返回:
            无

        异常:
            无直接异常
        """
        # 获取当前提示模式状态
        is_hint_mode = self.btn_hint.isChecked()

        # 根据模式切换视图拖拽模式
        # 提示模式下禁用拖拽，防止误操作
        self.view.setDragMode(QGraphicsView.NoDrag if is_hint_mode else QGraphicsView.ScrollHandDrag)

        # 根据模式切换光标样式
        # 提示模式使用十字光标，表示可以点击选择位置
        self.view.setCursor(Qt.CrossCursor if is_hint_mode else Qt.ArrowCursor)

        # 更新状态栏提示信息
        self.status_label.setText("请在地图上点击您当前的大致位置..." if is_hint_mode else "取消设置初始位置")

    def _calibrate_screen_center(self):
        """
        启动屏幕中心校准流程

        创建并显示全屏选择器窗口，允许用户点击屏幕上的任意位置
        作为游戏窗口的中心点。该坐标用于后续的运动控制计算。

        校准目的:
        - 确定游戏窗口的中心点坐标（物理像素）
        - 运动控制器使用该坐标计算移动方向

        返回:
            无

        异常:
            无直接异常
        """
        # 检查校准选择器是否已存在且可见
        if hasattr(self, 'center_selector') and self.center_selector.isVisible():
            # 已存在且可见，直接返回，防止重复创建
            return

        # 创建新的校准选择器
        self.center_selector = CenterPointSelector()
        # 连接点选择信号到处理函数
        self.center_selector.point_selected.connect(self._handle_calibration_click)
        # 全屏显示选择器
        self.center_selector.showFullScreen()

    def _handle_calibration_click(self, x, y):
        """
        处理屏幕中心校准点击事件

        将用户点击的逻辑坐标转换为物理坐标，保存到配置中，
        并自动保存配置到文件。

        参数:
            x (int): 点击位置的 X 坐标（逻辑坐标）
            y (int): 点击位置的 Y 坐标（逻辑坐标）

        返回:
            无

        异常:
            无直接异常
        """
        # 获取屏幕缩放系数
        screen = QApplication.primaryScreen()
        sx, sy = screen.devicePixelRatio(), screen.devicePixelRatio()

        # 将逻辑坐标转换为物理坐标
        physical_x = int(x * sx)  # X 坐标乘以缩放系数
        physical_y = int(y * sy)  # Y 坐标乘以缩放系数

        # 保存物理坐标到配置
        self.nav_config.game_screen_center = (physical_x, physical_y)

        # 打印调试信息
        print(f"Screen center calibrated at physical coordinates: {self.nav_config.game_screen_center}")

        # 更新参数对话框的 UI 显示
        # 传入 (0, 0) 作为虚拟物理中心，因为 UI 只需要显示逻辑坐标
        self.params_dialog.set_config_to_ui(self.nav_config, (0, 0))
        self._update_overlay_display()

        # 自动保存配置到文件
        self._save_nav_config()

        # 显示校准完成提示
        QMessageBox.information(self, "校准完成", f"屏幕中心已校准为：{self.nav_config.game_screen_center}")

        # 关闭校准选择器
        self.center_selector.close()


    def toggle_navigation(self):
        """
        切换导航的启动/停止状态

        启动导航时:
        1. 检查配置是否就绪（屏幕中心、监控中心、监控大小）
        2. 应用最新参数到核心模块
        3. 根据自动移动开关状态启用运动控制器
        4. 启动导航循环定时器

        停止导航时:
        1. 停止导航循环定时器
        2. 禁用运动控制器

        返回:
            无

        异常:
            无直接异常，配置不完整时弹出警告对话框
        """
        if self.btn_start.isChecked():
            self._use_unified_navigation_loop()
            # --- 启动导航 ---
            print("DEBUG: '开始导航' button clicked.")
            start_event_log_session("navigation")

            # 检查配置是否就绪
            if not self.nav_config.game_screen_center:
                # 未校准屏幕中心，提示用户
                QMessageBox.warning(self, "警告", "请先点击'校准屏幕中心'进行设置！")
                self.btn_start.setChecked(False)  # 重置按钮状态
                return

            if not self.nav_config or (not self.nav_config.monitor_logical_center and not self.nav_config.monitor_region) or not self.nav_config.monitor_size:
                # 地图配置不完整，提示用户
                QMessageBox.warning(self, "警告", "地图配置不完整，缺少监控中心或大小！")
                self.btn_start.setChecked(False)  # 重置按钮状态
                return

            # 应用最新参数到核心模块
            self._apply_config_to_core()
            self._current_player_local_pos = None
            if self.nav_core:
                self.nav_core.request_full_map_localization("navigation_start")
            if hasattr(self.app_context, 'tracker') and self.app_context.tracker:
                self.app_context.tracker.reset()

            # 计算定时器间隔（毫秒）
            # fps 表示每秒定位次数，interval = 1000 / fps
            interval = 1000 // self.nav_config.fps

            # 默认启用自动移动
            print("DEBUG: Auto-move enabled by default on navigation start.")
            self.motion_controller.set_control_enabled(True)

            # 启动导航循环定时器
            self.nav_timer.start(interval)  # 使用配置的 FPS

            # 更新 UI
            self.btn_start.setText("停止导航")  # 按钮文本改为"停止导航"
            self.status_label.setText("导航已开始...")  # 状态栏提示
            print("DEBUG: Navigation started.")
        else:
            # --- 停止导航 ---
            print("DEBUG: '停止导航' button clicked.")

            # 停止导航循环定时器
            self.nav_timer.stop()

            # 禁用运动控制器
            print("DEBUG: Disabling motion_controller.")
            self.motion_controller.set_control_enabled(False)

            # 重置首次定位标志，以便下次启动时重新触发
            if self.nav_core:
                self.nav_core.is_first_frame_localized = False
            self.auto_navigation_enabled = False
            if self.portal_test_controller.active:
                self._set_portal_manual_test_active(False, reason="navigation stopped")
            self.navigation_task_controller.stop()
            self._set_game_input_window_mode(False)
            self.btn_auto_nav.setChecked(False)
            self._render_route_overlay()

            # 更新 UI
            self.btn_start.setText("开始导航")  # 按钮文本改回"开始导航"
            self.status_label.setText("导航暂停")  # 状态栏提示
            print("DEBUG: Navigation stopped.")

    def _use_unified_navigation_loop(self) -> None:
        try:
            self.nav_timer.timeout.disconnect(self.navigation_loop)
        except (TypeError, RuntimeError):
            pass
        try:
            self.nav_timer.timeout.disconnect(self._navigation_loop_unified)
        except (TypeError, RuntimeError):
            pass
        self.nav_timer.timeout.connect(self._navigation_loop_unified)

    def _navigation_loop_unified(self):
        """Unified navigation loop: event observation + one task controller."""
        if not self.nav_config or (not self.nav_config.monitor_logical_center and not self.nav_config.monitor_region):
            return

        capture_rect, default_player_pos = self._build_capture_geometry()
        if not capture_rect:
            return
        self._current_capture_rect = capture_rect

        frame = self.app_context.screen_capture.capture(
            capture_rect["left"],
            capture_rect["top"],
            capture_rect["width"],
            capture_rect["height"],
        )
        if frame is None:
            return

        if self.nav_config.monitor_region:
            player_mask = self.nav_core.recognizer.extract_player(frame)
            player_pos = self.app_context.tracker.detect_player(player_mask)
            if player_pos is None:
                player_pos = self._current_player_local_pos or (
                    capture_rect["width"] // 2,
                    capture_rect["height"] // 2,
                )
        else:
            player_pos = default_player_pos
        self._current_player_local_pos = player_pos

        global_x, global_y, conf = self.nav_core.localize(frame, player_pos=player_pos)
        now_ms = int(time.time() * 1000)
        localized_pos = None if global_x is None or global_y is None else (global_x, global_y)
        event_tick = None
        if self.event_coordinator:
            event_tick = self._build_event_tick(now_ms, frame, player_pos, localized_pos, conf)
            self.event_coordinator.observe(event_tick)
            self._render_event_overlay()
            if self.event_dialog.isVisible():
                self.event_dialog.refresh_tasks()

        intent = None
        event_run_enabled = bool(self.auto_navigation_enabled or self.portal_test_controller.active)
        if event_run_enabled:
            lookahead = max(36.0, min(float(capture_rect["width"]) * self.nav_core.draw_scale * 0.18, 120.0))
            main_route = (self.route_data or {}).get("routes", {}).get("main", {})
            intent = self.navigation_task_controller.update(
                localized_pos=localized_pos,
                confidence=conf,
                route=main_route,
                event_coordinator=self.event_coordinator,
                event_tick=event_tick,
                wall_map=self.nav_core.nav_wall_layer,
                pathfinder=self.app_context.path_finder,
                explored_map=self.nav_core.explored_map,
                now_ms=now_ms,
                lookahead_distance=lookahead,
                manual_event_only=bool(self.portal_test_controller.active and not self.auto_navigation_enabled),
                frame_registration=getattr(self.nav_core, "last_frame_registration", None),
            )

        if global_x is not None and global_y is not None:
            offset_x, offset_y = self.nav_core.crop_offset
            display_x = global_x - offset_x
            display_y = global_y - offset_y
            if not self.player_item:
                self.player_item = self.scene.addEllipse(-5, -5, 10, 10, QPen(Qt.red), QBrush(Qt.red))
                self.player_item.setZValue(2)
            self.player_item.setPos(display_x, display_y)
            self.player_item.setVisible(True)
            self._update_monitor_rect((global_x, global_y), capture_rect=capture_rect, player_local_pos=player_pos)
            self._update_game_view_rect((global_x, global_y))
            status_text = (
                f"位置: ({int(global_x)}, {int(global_y)}) | 置信度: {conf:.2f} | "
                f"监视: {capture_rect['width']}x{capture_rect['height']}"
            )
            self.view.centerOn(display_x, display_y)
        else:
            fallback_pos = self.nav_core.last_good_pos or self.nav_core.drawing_saved_pos
            if fallback_pos:
                self._update_monitor_rect(
                    fallback_pos,
                    capture_rect=capture_rect,
                    player_local_pos=player_pos,
                )
                self._update_game_view_rect(fallback_pos)
            if self.player_item:
                self.player_item.setVisible(False)
            status_text = f"定位中... 监视: {capture_rect['width']}x{capture_rect['height']}"

        if intent:
            if intent.message:
                status_text += f" | 导航: {intent.message}"
            if intent.path_kind and intent.path_kind != "none":
                status_text += f" | path:{intent.path_kind}"
        event_status = self._event_status_text()
        if event_status:
            status_text += f" | {event_status}"
        self.status_label.setText(status_text)

        if intent:
            self._render_route_overlay(
                current_path=intent.path,
                current_subgoal=intent.subgoal,
                current_required_index=intent.required_index,
                current_guide_index=None,
                current_target_kind=intent.task_kind,
            )
            if intent.metadata.get("force_relocalize"):
                reason = intent.metadata.get("relocalize_reason") or "coordinate_recovery"
                self.nav_core.request_global_relocalization(reason)
                event_log(
                    "navigation forced global relocalization",
                    reason=reason,
                    score=intent.metadata.get("relocalize_score"),
                    player=intent.player_pos,
                    task=intent.task_id,
                )
                self.status_label.setText(f"{self.status_label.text()} | 正在重新定位")
                return
            self._execute_navigation_intent(intent, now_ms)
            if intent.metadata.get("terminal") and self.portal_test_controller.active:
                self._set_portal_manual_test_active(False, reason=intent.message)
            if intent.type == NavigationIntentType.ARRIVED:
                self.auto_navigation_enabled = False
                self.navigation_task_controller.stop()
                self._set_game_input_window_mode(False)
                self.btn_auto_nav.setChecked(False)
                self.status_label.setText("已到达出口区域")
            elif intent.type == NavigationIntentType.FAILED:
                self.auto_navigation_enabled = False
                self.navigation_task_controller.stop()
                self._set_game_input_window_mode(False)
                self.btn_auto_nav.setChecked(False)
                self.status_label.setText(intent.message or "自动导航失败")
        elif self.route_data:
            self._render_route_overlay()

    def _execute_navigation_intent(self, intent, now_ms: int) -> None:
        if intent is None or intent.type in (NavigationIntentType.NONE, NavigationIntentType.WAIT):
            return
        if intent.type == NavigationIntentType.MOVE_MAP:
            if not intent.player_pos or not intent.subgoal:
                return
            self._set_game_input_window_mode(True)
            self.motion_controller.set_control_enabled(True)
            if intent.metadata.get("force_click_target"):
                click_info = self.motion_controller.click_map_target_once(
                    intent.player_pos,
                    intent.subgoal,
                    reason=intent.message or "navigation_forced_target",
                )
            else:
                click_info = self.motion_controller.move_to_map_target(
                    intent.player_pos,
                    intent.subgoal,
                )
            if click_info:
                self.navigation_task_controller.record_intent_click(intent, now_ms)
                self.status_label.setText(
                    f"{self.status_label.text()} | "
                    f"click r:{click_info['screen_radius']:.0f}/"
                    f"raw:{click_info.get('raw_screen_radius', 0):.0f}"
                )
            return
        if intent.type == NavigationIntentType.CLICK_SCREEN:
            screen_pos = intent.metadata.get("screen_pos")
            if screen_pos:
                self._set_game_input_window_mode(True)
                self.motion_controller.click_screen_position(screen_pos, reason=intent.message or "navigation_event_click")
            return
        if intent.type == NavigationIntentType.PRESS_KEY:
            key = intent.metadata.get("key")
            if key:
                self._set_game_input_window_mode(True)
                self.motion_controller.press_key(key, reason=intent.message or "navigation_event_key")
            return

    def navigation_loop(self):
        """Compatibility entry point for the Qt timer; all logic lives in the unified loop."""
        return self._navigation_loop_unified()

    def _event_status_text(self) -> str:
        return event_status_text(self.event_coordinator)
