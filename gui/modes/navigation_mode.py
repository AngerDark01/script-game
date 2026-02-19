"""
导航模式模块 - 提供游戏内自动导航功能的主界面

本模块实现了基于地图匹配的玩家位置实时定位和导航功能，
支持手动设置初始位置、自动路径跟踪、屏幕中心校准等功能。
"""

import os
import json
import cv2
import numpy as np
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QComboBox, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
    QMessageBox, QGraphicsPathItem, QCheckBox, QApplication
)
from PySide6.QtCore import Qt, QTimer, QPointF, QEvent, QPoint
from PySide6.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QBrush, QPainterPath

from core.navigation_core import NavigationCore
from core.motion_controller import MotionController
from ..selection.indicator_overlay import OverlayWindow
from ..selection.center_selector import CenterPointSelector
from ..dialogs.nav_params_dialog import NavParametersDialog
from ..navigation_params import NavConfig

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

        self.init_ui()  # 初始化用户界面，创建所有 UI 控件
        self._connect_signals()  # 连接 UI 控件的信号到对应的槽函数

        self.nav_timer = QTimer()  # 导航循环定时器，按固定频率执行定位和移动
        self.nav_timer.timeout.connect(self.navigation_loop)  # 连接定时器超时信号到导航循环函数

        # 缓存物理坐标，避免每次循环重复计算
        # 存储格式：(center_x, center_y)，单位为物理像素
        self._capture_center_physical = None

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

        self.chk_auto_move = QCheckBox("启用自动移动")  # 自动移动开关，启用后自动模拟键盘移动
        top_bar.addWidget(self.chk_auto_move)

        self.calibrate_button = QPushButton("校准屏幕中心")  # 屏幕中心校准按钮，用于确定游戏窗口的中心点坐标
        top_bar.addWidget(self.calibrate_button)

        self.params_button = QPushButton("⚙️ 参数面板")  # 打开参数配置面板按钮
        top_bar.addWidget(self.params_button)
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
        self.chk_auto_move.stateChanged.connect(self.toggle_auto_move)  # 自动移动复选框 -> toggle_auto_move 函数
        self.params_button.clicked.connect(self.toggle_params_dialog)  # 参数面板按钮 -> toggle_params_dialog 函数
        self.calibrate_button.clicked.connect(self._calibrate_screen_center)  # 校准按钮 -> _calibrate_screen_center 函数

        # 连接参数对话框的信号
        self.params_dialog.parameters_changed.connect(self._on_parameter_changed)  # 参数变化信号 -> _on_parameter_changed 函数
        self.params_dialog.save_requested.connect(self._save_nav_config)  # 保存请求信号 -> _save_nav_config 函数
        self.params_dialog.nav_toggle_overlay_btn.clicked.connect(self._toggle_overlay_display)  # 幕布切换按钮 -> _toggle_overlay_display 函数

    def toggle_params_dialog(self):
        """
        切换参数配置对话框的显示/隐藏状态

        如果对话框当前可见则隐藏，否则显示对话框。
        用于响应用户点击"参数面板"按钮的操作。

        返回:
            无

        异常:
            无
        """
        if self.params_dialog.isVisible():
            # 对话框当前可见，隐藏它
            self.params_dialog.hide()
        else:
            # 对话框当前隐藏，显示它
            self.params_dialog.show()

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

        # 计算 map_data 文件夹的绝对路径
        current_dir = os.path.dirname(os.path.abspath(__file__))  # 获取当前文件所在目录
        project_root = os.path.dirname(os.path.dirname(current_dir))  # 获取项目根目录（向上两级）
        map_data_dir = os.path.join(project_root, "map_data")  # 拼接 map_data 文件夹路径

        if os.path.exists(map_data_dir):
            # map_data 文件夹存在，列出所有子目录作为可选地图
            dirs = [d for d in os.listdir(map_data_dir) if os.path.isdir(os.path.join(map_data_dir, d))]
            self.map_combo.addItems(dirs)  # 将所有地图名称添加到下拉框
        else:
            # map_data 文件夹不存在，显示提示信息
            self.map_combo.addItem("未找到 map_data 文件夹")

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
        if not map_name or map_name == "未找到 map_data 文件夹":
            # 没有有效地图选中，直接返回
            return

        # 构建地图文件夹的绝对路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir))
        self.map_folder_path = os.path.join(project_root, "map_data", map_name)

        try:
            # 尝试读取地图配置文件
            config_path = os.path.join(self.map_folder_path, "config.json")
            if os.path.exists(config_path):
                # 配置文件存在，读取配置
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_dict = json.load(f)
                    self.nav_config = NavConfig.from_dict(config_dict)  # 从字典创建 NavConfig 对象
            else:
                # 配置文件不存在，使用默认配置并提示用户
                self.nav_config = NavConfig()  # 使用默认配置
                QMessageBox.warning(self, "警告", "未找到 config.json，将使用默认参数。")

            # 初始化导航核心引擎，加载地图图像和特征
            self.nav_core = NavigationCore(self.map_folder_path)
            self._apply_config_to_core()  # 将配置参数应用到核心模块

            # 计算物理坐标并缓存（避免 navigation_loop 重复计算）
            sx, sy = self._compute_scale()
            logical_x, logical_y = self.nav_config.monitor_logical_center
            self._capture_center_physical = (int(logical_x * sx), int(logical_y * sy))
            print(f"地图 '{map_name}' 加载完成，物理坐标：{self._capture_center_physical}")

            # 实时计算物理坐标以更新 UI
            px, py = self._capture_center_physical
            self.params_dialog.set_config_to_ui(self.nav_config, (px, py))

            self._render_map()  # 渲染地图到图形视图

            # 显示上次退出的位置（从 npz 文件的 current_pos 加载）
            self._show_last_exit_position()

            # 启用功能按钮
            self.btn_start.setEnabled(True)  # 启用开始导航按钮
            self.btn_hint.setEnabled(True)  # 启用设置初始位置按钮
            self.status_label.setText(f"地图 '{map_name}' 加载成功。请设置初始位置或直接开始导航。")

        except Exception as e:
            # 捕获任何异常并显示错误对话框
            QMessageBox.critical(self, "错误", f"加载地图失败：{str(e)}")

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

        # 调整视图
        self.view.fitInView(self.map_item, Qt.KeepAspectRatio)

    def _update_monitor_rect(self, player_pos):
        """
        根据传入的玩家位置和配置更新监控区域矩形框（绿框）。

        该方法从导航核心和配置中获取必要参数，计算绿框在场景中的
        正确位置和大小，并更新其可见性。
        """
        if not all([self.monitor_rect_item, player_pos, self.nav_core, self.nav_config]):
            return

        # 1. 获取必要参数
        draw_scale = self.nav_core.draw_scale
        monitor_width = self.nav_config.monitor_size
        monitor_height = self.nav_config.monitor_size
        offset_x, offset_y = self.nav_core.crop_offset

        # 2. 计算绿框的尺寸
        rect_w = monitor_width / draw_scale
        rect_h = monitor_height / draw_scale

        # 3. 计算绿框的左上角坐标 (将玩家位置从中心点转换过来)
        rect_x = (player_pos[0] - offset_x) - rect_w / 2
        rect_y = (player_pos[1] - offset_y) - rect_h / 2

        # 4. 更新矩形框并设为可见
        self.monitor_rect_item.setRect(rect_x, rect_y, rect_w, rect_h)
        if not self.monitor_rect_item.isVisible():
            self.monitor_rect_item.setVisible(True)

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
        if not self.nav_core or not self.nav_core.last_pos:
            print("没有上次退出的位置信息")
            return

        # 获取上次退出的全局坐标
        last_pos_global = self.nav_core.last_pos
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
        self.nav_core.draw_scale = self.nav_config.draw_scale  # 设置绘制缩放系数

        # 2. 更新地图裁剪偏移量
        # 调用 get_map_image() 会重新计算 crop_offset
        # 这确保了在 draw_scale 改变后，显示坐标仍然正确
        self.nav_core.get_map_image()

        # 3. 更新运动控制器参数
        # 只有在配置了屏幕中心坐标时才更新运动控制器
        if self.nav_config.game_screen_center:
            self.motion_controller.set_params(
                game_screen_center=self.nav_config.game_screen_center,  # 游戏屏幕中心坐标（物理像素）
                movement_scale_factor=self.nav_config.movement_scale_factor  # 移动缩放系数，用于调整移动距离
            )

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

        # 保存当前配置中不应被 UI 修改的关键部分
        # nav_preferences 包含导航偏好设置，不应被参数对话框覆盖
        original_nav_prefs = self.nav_config.nav_preferences

        # 更新为从 UI 传来的新配置
        self.nav_config = new_config

        # 恢复被覆盖的关键部分
        # 确保导航偏好设置不被 UI 修改
        self.nav_config.nav_preferences = original_nav_prefs

        # 更新参数对话框的状态标签，提示用户有未保存的修改
        self.params_dialog.nav_status_label.setText("有未保存的修改")

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

        # 构建配置文件路径
        config_path = os.path.join(self.map_folder_path, "config.json")
        try:
            # 1. 将当前配置写入文件
            # 使用 indent=4 格式化输出，ensure_ascii=False 支持中文
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.nav_config.to_dict(), f, indent=4, ensure_ascii=False)

            # 2. 将这套完整的配置应用到核心模块
            self._apply_config_to_core()

            # 3. 更新 UI 状态
            self.params_dialog.nav_status_label.setText("参数已保存并应用")
            QMessageBox.information(self, "成功", "参数已保存并成功应用到当前导航。")

        except Exception as e:
            # 捕获写入异常并显示错误对话框
            QMessageBox.critical(self, "保存失败", f"无法写入 config.json: {e}")
            self.params_dialog.nav_status_label.setText("保存失败!")

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
        if not self.nav_config or not self.nav_config.monitor_logical_center:
            # 配置无效，重置按钮状态并提示用户
            self.params_dialog.nav_toggle_overlay_btn.setChecked(False)
            QMessageBox.warning(self, "警告", "地图配置不完整，无法显示幕布。")
            return

        # 切换显示状态
        if self.params_dialog.nav_toggle_overlay_btn.isChecked():
            # 按钮被选中，显示幕布
            # 直接使用逻辑坐标进行绘制
            if self.nav_config.monitor_logical_center:
                center_logical_x, center_logical_y = self.nav_config.monitor_logical_center  # 获取逻辑中心坐标
                size_px = self.nav_config.monitor_size  # 获取监控区域大小（物理像素）

                # 尺寸仍然需要从物理像素转换为逻辑像素
                sx, _ = self._compute_scale()  # 获取缩放系数
                size_logical = int(size_px / sx)  # 转换为逻辑尺寸

                # 显示幕布，使用逻辑坐标
                self.overlay.set_geometry_and_show(center_logical_x, center_logical_y, size_logical)
            else:
                # 配置中缺少逻辑中心点，提示用户
                QMessageBox.warning(self, "警告", "配置中缺少逻辑中心点 (monitor_logical_center)，无法显示幕布。")
                self.params_dialog.nav_toggle_overlay_btn.setChecked(False)
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
        """
        处理地图上的鼠标点击事件

        根据当前模式执行不同操作:
        1. 提示模式 (btn_hint 选中): 设置初始位置提示
        2. 导航模式 (btn_hint 未选中): 点击地图目标位置进行移动

        参数:
            pos (QPointF): 点击位置的场景坐标（逻辑坐标，已考虑 DPR）

        返回:
            无

        异常:
            无直接异常，导航核心未初始化或定位失败时弹出警告对话框
        """
        # 检查导航核心是否已初始化
        if not self.nav_core:
            return

        # 获取地图裁剪偏移量（用于将显示坐标转换为地图全局坐标）
        offset_x, offset_y = self.nav_core.crop_offset
        # 将场景坐标转换为地图全局坐标
        target_x = pos.x() + offset_x  # X 坐标加上偏移量
        target_y = pos.y() + offset_y  # Y 坐标加上偏移量

        if self.btn_hint.isChecked():
            # --- 提示模式：设置初始位置 ---
            # 将初始位置提示传递给导航核心
            self.nav_core.set_initial_hint((target_x, target_y))

            # 创建或获取提示标记项（蓝色圆点）
            if not self.hint_item:
                self.hint_item = self.scene.addEllipse(0, 0, 10, 10, QPen(Qt.blue), QBrush(Qt.blue))
                self.hint_item.setZValue(2.5)  # 设置最高层级，确保在其他标记之上

            # 设置提示标记位置并显示
            self.hint_item.setPos(pos)  # 使用场景坐标（显示坐标）
            self.hint_item.setVisible(True)

            # 在设置初始提示时，也更新监控框的位置，提供即时反馈
            self._update_monitor_rect((target_x, target_y))

            print(f"=== 初始位置提示已设置 (用户点击): ({int(target_x)}, {int(target_y)}) ===")
            self.status_label.setText(f"初始位置提示已设置：({int(target_x)}, {int(target_y)})。")

            # 重置提示按钮状态
            self.btn_hint.setChecked(False)
            self.toggle_hint_mode()
        else:
            # --- 导航模式：点击地图目标位置进行移动 ---
            # 检查是否已定位成功
            if not self.nav_core.is_localized or not self.nav_core.current_pos:
                # 未定位成功，提示用户
                QMessageBox.warning(self, "警告", "请先开始导航并等待定位成功。")
                return

            # 计算目标全局坐标和玩家当前全局坐标
            target_global_pos = (target_x, target_y)  # 目标位置（地图全局坐标）
            player_global_pos = self.nav_core.current_pos  # 玩家当前位置（地图全局坐标）

            # 调用运动控制器执行移动
            # 运动控制器会根据两个坐标计算移动方向和距离
            self.motion_controller.move_to_map_target(player_global_pos, target_global_pos)

            # 显示目标标记
            self.target_item.setPos(pos)  # 使用场景坐标（显示坐标）
            self.target_item.setVisible(True)
            self.status_label.setText(f"目标已更新: ({pos.x():.1f}, {pos.y():.1f})")

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

        # 自动保存配置到文件
        self._save_nav_config()

        # 显示校准完成提示
        QMessageBox.information(self, "校准完成", f"屏幕中心已校准为：{self.nav_config.game_screen_center}")

        # 关闭校准选择器
        self.center_selector.close()

    def toggle_auto_move(self, state):
        """
        切换自动移动功能的启用状态

        此方法响应自动移动复选框的状态变化。
        仅当导航正在进行时，才真正启用/禁用运动控制器。

        参数:
            state (Qt.CheckState): 复选框的新状态
                - Qt.Checked (2): 已选中，启用自动移动
                - Qt.Unchecked (0): 未选中，禁用自动移动
                - Qt.PartiallyChecked (1): 部分选中（三方框状态，此处不使用）

        返回:
            无

        异常:
            无直接异常
        """
        # 判断是否启用（状态为选中）
        enabled = (state == Qt.Checked)
        # 打印调试信息
        print(f"DEBUG: '自动移动' checkbox toggled. New state: {enabled}. Navigation active: {self.nav_timer.isActive()}")

        # 仅当导航正在进行时，才真正启用/禁用运动控制器
        if self.nav_timer.isActive():
            # 导航正在进行，设置运动控制器的启用状态
            print(f"DEBUG: Navigation is active. Setting motion_controller enabled to {enabled}")
            self.motion_controller.set_control_enabled(enabled)

            if enabled:
                # 启用时显示提示信息
                QMessageBox.information(self, "提示", "自动移动已启用！")

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
            # --- 启动导航 ---
            print("DEBUG: '开始导航' button clicked.")

            # 检查配置是否就绪
            if not self.nav_config.game_screen_center:
                # 未校准屏幕中心，提示用户
                QMessageBox.warning(self, "警告", "请先点击'校准屏幕中心'进行设置！")
                self.btn_start.setChecked(False)  # 重置按钮状态
                return

            if not self.nav_config or not self.nav_config.monitor_logical_center or not self.nav_config.monitor_size:
                # 地图配置不完整，提示用户
                QMessageBox.warning(self, "警告", "地图配置不完整，缺少监控中心或大小！")
                self.btn_start.setChecked(False)  # 重置按钮状态
                return

            # 应用最新参数到核心模块
            self._apply_config_to_core()

            # 计算定时器间隔（毫秒）
            # fps 表示每秒定位次数，interval = 1000 / fps
            interval = 1000 // self.nav_config.fps

            # 获取自动移动开关状态
            is_auto_move_checked = self.chk_auto_move.isChecked()
            print(f"DEBUG: '自动移动' checkbox is checked: {is_auto_move_checked}")
            print(f"DEBUG: Setting motion_controller enabled to {is_auto_move_checked}")

            # 设置运动控制器的启用状态
            self.motion_controller.set_control_enabled(is_auto_move_checked)

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

            # 更新 UI
            self.btn_start.setText("开始导航")  # 按钮文本改回"开始导航"
            self.status_label.setText("导航暂停")  # 状态栏提示
            print("DEBUG: Navigation stopped.")

    def navigation_loop(self):
        """
        导航循环函数，定时执行定位和移动

        此方法由导航定时器 (nav_timer) 按固定频率调用，执行以下操作:
        1. 检查配置是否有效
        2. 使用缓存的物理坐标进行屏幕截图（避免重复计算）
        3. 调用导航核心进行位置定位
        4. 更新玩家位置标记的显示
        5. 更新监控区域矩形框的位置
        6. 更新状态栏显示定位结果
        7. 调整视图中心到玩家位置

        调用频率:
            由 nav_config.fps 决定，默认 1000 // fps 毫秒调用一次

        返回:
            无

        异常:
            无直接异常，截图失败时静默返回
        """
        # 检查配置是否有效
        if not self.nav_config or not self.nav_config.monitor_logical_center:
            return

        # 使用缓存的物理坐标进行截图（避免每次循环重复计算）
        if self._capture_center_physical is None:
            # 如果缓存为空，重新计算物理坐标
            sx, sy = self._compute_scale()  # 获取屏幕缩放系数
            logical_x, logical_y = self.nav_config.monitor_logical_center  # 获取逻辑中心坐标
            self._capture_center_physical = (int(logical_x * sx), int(logical_y * sy))  # 转换为物理坐标并缓存

        # 获取缓存的物理中心坐标
        center_x, center_y = self._capture_center_physical
        # 获取监控区域大小
        size = self.nav_config.monitor_size

        # 执行屏幕截图
        # 从应用程序上下文获取屏幕截图服务，截取指定中心点和大小的正方形区域
        frame = self.app_context.screen_capture.capture_square(center_x, center_y, size)
        if frame is None:
            # 截图失败，直接返回
            return

        # 调用导航核心进行位置定位
        # 输入：当前屏幕截图帧
        # 输出：全局地图坐标 (global_x, global_y) 和置信度 conf
        global_x, global_y, conf = self.nav_core.localize(frame)

        if global_x is not None:
            # --- 定位成功 ---
            # 获取地图裁剪偏移量
            offset_x, offset_y = self.nav_core.crop_offset

            # 将全局坐标转换为显示坐标（减去裁剪偏移量）
            display_x = global_x - offset_x
            display_y = global_y - offset_y

            # 更新玩家位置标记
            if not self.player_item:
                self.player_item = self.scene.addEllipse(-5, -5, 10, 10, QPen(Qt.red), QBrush(Qt.red))
                self.player_item.setZValue(2)

            # 检查是否是首次定位成功
            # 使用 nav_core 的 is_first_frame_localized 标志来确保只打印一次
            if hasattr(self.nav_core, 'is_first_frame_localized') and self.nav_core.is_first_frame_localized:
                print(f"=== 第一帧定位成功 (实时人物位置): ({int(global_x)}, {int(global_y)}) | 置信度：{conf:.2f} ===")
                print(f"=== 三个位置标记对比 ===")
                if self.nav_core.last_pos:
                    print(f"  1. 上次退出位置 (绘图模式): ({self.nav_core.last_pos[0]:.2f}, {self.nav_core.last_pos[1]:.2f})")
                if self.nav_core.current_pos and self.nav_core.current_pos != self.nav_core.last_pos:
                    print(f"  2. 初始位置提示 (用户点击): ({self.nav_core.current_pos[0]:.2f}, {self.nav_core.current_pos[1]:.2f})")
                print(f"  3. 实时人物位置 (第一帧定位): ({int(global_x)}, {int(global_y)})")
                print(f"=========================")

            self.player_item.setPos(display_x, display_y)
            self.player_item.setVisible(True)

            # 使用当前位置更新监控区域
            self._update_monitor_rect((global_x, global_y))

            # 更新状态栏显示定位结果
            status_text = f"位置：({int(global_x)}, {int(global_y)}) | 置信度：{conf:.2f}"
            self.status_label.setText(status_text)

            # 调整视图中心到玩家位置
            self.view.centerOn(display_x, display_y)
        else:
            # --- 定位失败 ---
            # 即使定位失败，也尝试使用上一个有效位置更新绿框，让用户知道正在监控哪个区域
            if self.nav_core.last_known_pos:
                self._update_monitor_rect(self.nav_core.last_known_pos)

            # 更新状态栏提示
            self.status_label.setText("定位丢失...")

            # 隐藏玩家位置标记
            if self.player_item:
                self.player_item.setVisible(False)

            # 定位失败时不再隐藏监控绿框
