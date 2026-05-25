"""
导航参数对话框模块

本模块提供了一个用于配置和显示导航参数的对话框界面。
该对话框允许用户调整导航相关的各种参数，包括：
- HSV 颜色识别范围（墙体、迷雾、玩家）
- 图像处理算法开关（CLAHE、Gamma 校正、顶帽变换等）
- 算法数值参数（阈值、权重、核大小等）
- 地图与运动控制参数

该对话框通过 Qt 信号与外部组件通信，当参数发生变化时会自动发出信号。

依赖模块:
    - PySide6: Qt GUI 框架
    - gui.navigation_params: 导航配置数据类
"""

import ast
import functools
import dataclasses
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QGroupBox, QFormLayout, QGridLayout, QHBoxLayout,
    QApplication, QPushButton, QLabel, QSpinBox, QDoubleSpinBox, QCheckBox,
    QLineEdit, QWidget, QTabWidget
)
from PySide6.QtCore import Qt, Signal, QSignalBlocker

from gui.navigation_params import NavConfig, NavPreferences, RecognizerParams, _parse_hsv_list


class NavParametersDialog(QDialog):
    """
    导航参数配置对话框

    这是一个独立的对话框窗口，用于显示和编辑导航系统的各项参数。
    对话框包含三个主要区域：
    1. 识别参数区：HSV 颜色范围设置
    2. 算法开关区：各种图像处理算法的启用/禁用开关
    3. 算法数值区：算法相关的数值参数调节
    4. 地图与运动控制区：显示只读信息和运动控制参数

    该类通过 Qt 信号机制与外部通信：
    - parameters_changed: 当参数发生变化时发出，携带新的 NavConfig 对象
    - save_requested: 当用户点击保存按钮时发出

    属性:
        parameters_changed (Signal): 参数变化信号，参数类型为 NavConfig
        save_requested (Signal): 保存请求信号

    示例:
        >>> dialog = NavParametersDialog(parent_widget)
        >>> dialog.parameters_changed.connect(on_params_changed)
        >>> dialog.show()
    """

    # 参数变化信号，当任何 UI 控件值改变时发出，携带新的导航配置对象
    parameters_changed = Signal(NavConfig)
    # 保存请求信号，当用户点击保存按钮时发出
    save_requested = Signal()
    save_default_requested = Signal()

    def __init__(self, parent=None):
        """
        初始化导航参数对话框

        参数:
            parent (QWidget, optional): 父窗口部件。默认为 None。
        """
        super().__init__(parent)
        self.setWindowTitle("导航参数面板")
        # 设置为非模态对话框，允许与其他窗口同时交互
        self.setModal(False)
        
        # 用于存储当前对话框所代表的完整 `NavConfig` 对象
        self.config: NavConfig | None = None
        self._action_buttons_connected = False
        self._signals_connected = False

        # 初始化用户界面
        self._init_ui()
        # 连接所有信号和槽
        self._connect_signals()

    def _init_ui(self):
        """
        初始化用户界面布局

        创建并布局所有 UI 控件，包括：
        - 识别参数组（HSV 颜色范围输入框）
        - 算法开关组（复选框）
        - 算法数值组（数值输入框）
        - 地图与运动控制组（只读信息和控制按钮）
        - 动作和状态栏（保存按钮和状态标签）
        """
        # 创建主布局
        dialog_layout = QVBoxLayout(self)
        self.nav_tabs = QTabWidget()
        dialog_layout.addWidget(self.nav_tabs, 1)

        positioning_tab = QWidget()
        positioning_layout = QVBoxLayout(positioning_tab)
        recognition_tab = QWidget()
        recognition_layout = QVBoxLayout(recognition_tab)
        movement_tab = QWidget()
        movement_layout = QVBoxLayout(movement_tab)
        path_tab = QWidget()
        path_layout = QVBoxLayout(path_tab)
        event_tab = QWidget()
        event_layout = QVBoxLayout(event_tab)
        map_tab = QWidget()
        map_layout = QVBoxLayout(map_tab)

        self.nav_tabs.addTab(positioning_tab, "定位识别")
        self.nav_tabs.addTab(recognition_tab, "识别算法")
        self.nav_tabs.addTab(movement_tab, "移动点击")
        self.nav_tabs.addTab(path_tab, "路径/A*")
        self.nav_tabs.addTab(event_tab, "事件靠近")
        self.nav_tabs.addTab(map_tab, "地图/调试")

        # ==================== 可调节参数区域 ====================
        # 创建识别参数组，用于设置 HSV 颜色识别范围
        adjustable_group = QGroupBox("识别参数")
        hsv_layout = QFormLayout(adjustable_group)

        # 创建 HSV 范围输入框（墙体、迷雾、玩家各一组）
        self.nav_wall_hsv_min_edit = QLineEdit()
        self.nav_wall_hsv_max_edit = QLineEdit()
        self.nav_fog_hsv_min_edit = QLineEdit()
        self.nav_fog_hsv_max_edit = QLineEdit()
        self.nav_player_hsv_min_edit = QLineEdit()
        self.nav_player_hsv_max_edit = QLineEdit()

        # 将输入框添加到布局中
        hsv_layout.addRow("墙体 HSV Min:", self.nav_wall_hsv_min_edit)
        hsv_layout.addRow("墙体 HSV Max:", self.nav_wall_hsv_max_edit)
        hsv_layout.addRow("迷雾 HSV Min:", self.nav_fog_hsv_min_edit)
        hsv_layout.addRow("迷雾 HSV Max:", self.nav_fog_hsv_max_edit)
        hsv_layout.addRow("玩家 HSV Min:", self.nav_player_hsv_min_edit)
        hsv_layout.addRow("玩家 HSV Max:", self.nav_player_hsv_max_edit)

        positioning_layout.addWidget(adjustable_group)

        # ==================== 算法开关区域 ====================
        # 创建算法开关组，用于启用/禁用各种图像处理算法
        flags_group = QGroupBox("算法开关 (Flags)")
        flags_layout = QGridLayout(flags_group)

        # 创建复选框
        self.nav_chk_enable_wall = QCheckBox("启用墙体识别")
        self.nav_chk_enable_fog = QCheckBox("启用迷雾识别")
        self.nav_chk_clahe_enabled = QCheckBox("启用 CLAHE")
        self.nav_chk_deepen_enabled = QCheckBox("启用颜色深化")
        self.nav_chk_gamma_enabled = QCheckBox("启用 Gamma 校正")
        self.nav_chk_tophat_enabled = QCheckBox("启用顶帽变换")
        self.nav_chk_sat_filter_enabled = QCheckBox("启用饱和度过滤")
        self.nav_chk_transparent_mode = QCheckBox("启用透明模式")

        # 使用网格布局排列复选框（2 列）
        flags_layout.addWidget(self.nav_chk_enable_wall, 0, 0)
        flags_layout.addWidget(self.nav_chk_enable_fog, 0, 1)
        flags_layout.addWidget(self.nav_chk_clahe_enabled, 1, 0)
        flags_layout.addWidget(self.nav_chk_deepen_enabled, 1, 1)
        flags_layout.addWidget(self.nav_chk_gamma_enabled, 2, 0)
        flags_layout.addWidget(self.nav_chk_tophat_enabled, 2, 1)
        flags_layout.addWidget(self.nav_chk_sat_filter_enabled, 3, 0)
        flags_layout.addWidget(self.nav_chk_transparent_mode, 3, 1)

        positioning_layout.addWidget(flags_group)
        positioning_layout.addStretch(1)

        # ==================== 算法数值区域 ====================
        # 创建算法数值组，用于调节各种算法的参数值
        numerical_group = QGroupBox("算法数值 (Values)")
        numerical_layout = QFormLayout(numerical_group)

        # 创建数值输入框，设置范围和步长
        # CLAHE 对比度限制参数
        self.nav_clahe_clip_spin = QDoubleSpinBox()
        self.nav_clahe_clip_spin.setRange(1.0, 10.0)
        self.nav_clahe_clip_spin.setSingleStep(0.5)

        # 颜色深化因子
        self.nav_deepen_factor_spin = QDoubleSpinBox()
        self.nav_deepen_factor_spin.setRange(0.1, 2.0)
        self.nav_deepen_factor_spin.setSingleStep(0.1)

        # Gamma 校正值
        self.nav_gamma_value_spin = QDoubleSpinBox()
        self.nav_gamma_value_spin.setRange(0.1, 5.0)
        self.nav_gamma_value_spin.setSingleStep(0.1)

        # 顶帽变换强度
        self.nav_tophat_strength_spin = QDoubleSpinBox()
        self.nav_tophat_strength_spin.setRange(0.0, 10.0)
        self.nav_tophat_strength_spin.setSingleStep(0.5)

        # 顶帽变换核大小
        self.nav_tophat_kernel_size_spin = QSpinBox()
        self.nav_tophat_kernel_size_spin.setRange(1, 31)
        self.nav_tophat_kernel_size_spin.setSingleStep(2)

        # 饱和度过滤阈值
        self.nav_sat_filter_thresh_spin = QSpinBox()
        self.nav_sat_filter_thresh_spin.setRange(0, 255)
        self.nav_sat_filter_thresh_spin.setSingleStep(5)

        # Canny 边缘检测低阈值
        self.nav_edge_low_spin = QSpinBox()
        self.nav_edge_low_spin.setRange(0, 255)
        self.nav_edge_low_spin.setSingleStep(5)

        # Canny 边缘检测高阈值
        self.nav_edge_high_spin = QSpinBox()
        self.nav_edge_high_spin.setRange(0, 255)
        self.nav_edge_high_spin.setSingleStep(5)

        # 蓝色通道增强因子
        self.nav_blue_boost_spin = QDoubleSpinBox()
        self.nav_blue_boost_spin.setRange(0.1, 3.0)
        self.nav_blue_boost_spin.setSingleStep(0.1)

        # 透明模式饱和度惩罚值
        self.nav_trans_sat_penalty_spin = QDoubleSpinBox()
        self.nav_trans_sat_penalty_spin.setRange(0.0, 5.0)
        self.nav_trans_sat_penalty_spin.setSingleStep(0.1)

        # 透明模式墙体阈值
        self.nav_trans_wall_thresh_spin = QSpinBox()
        self.nav_trans_wall_thresh_spin.setRange(0, 255)
        self.nav_trans_wall_thresh_spin.setSingleStep(1)

        # 饱和度过滤半径
        self.nav_sat_filter_radius_spin = QSpinBox()
        self.nav_sat_filter_radius_spin.setRange(0, 100)
        self.nav_sat_filter_radius_spin.setSingleStep(5)

        # 墙体权重
        self.nav_wall_weight_spin = QSpinBox()
        self.nav_wall_weight_spin.setRange(0, 100)
        self.nav_wall_weight_spin.setSingleStep(5)

        # 边缘权重
        self.nav_edge_weight_spin = QSpinBox()
        self.nav_edge_weight_spin.setRange(0, 100)
        self.nav_edge_weight_spin.setSingleStep(5)

        # CLAHE 网格大小
        self.nav_clahe_grid_spin = QSpinBox()
        self.nav_clahe_grid_spin.setRange(2, 16)
        self.nav_clahe_grid_spin.setSingleStep(1)

        # 小核大小（用于形态学操作）
        self.nav_kernel_small_spin = QSpinBox()
        self.nav_kernel_small_spin.setRange(1, 15)
        self.nav_kernel_small_spin.setSingleStep(2)

        # 中核大小（用于形态学操作）
        self.nav_kernel_medium_spin = QSpinBox()
        self.nav_kernel_medium_spin.setRange(1, 15)
        self.nav_kernel_medium_spin.setSingleStep(2)

        # 导航偏好参数 (已废弃，保留兼容)
        self.nav_k_ratio_spin = QDoubleSpinBox()
        self.nav_k_ratio_spin.setRange(0.1, 20.0)
        self.nav_k_ratio_spin.setSingleStep(0.5)
        self.nav_y_bias_spin = QDoubleSpinBox()
        self.nav_y_bias_spin.setRange(0.1, 20.0)
        self.nav_y_bias_spin.setSingleStep(0.5)

        # 将数值输入框添加到布局中
        numerical_layout.addRow("CLAHE Clip:", self.nav_clahe_clip_spin)
        numerical_layout.addRow("Deepen Factor:", self.nav_deepen_factor_spin)
        numerical_layout.addRow("Gamma Value:", self.nav_gamma_value_spin)
        numerical_layout.addRow("TopHat Strength:", self.nav_tophat_strength_spin)
        numerical_layout.addRow("TopHat Kernel Size:", self.nav_tophat_kernel_size_spin)
        numerical_layout.addRow("Sat Filter Thresh:", self.nav_sat_filter_thresh_spin)
        numerical_layout.addRow("Canny Low:", self.nav_edge_low_spin)
        numerical_layout.addRow("Canny High:", self.nav_edge_high_spin)
        numerical_layout.addRow("Blue Boost:", self.nav_blue_boost_spin)
        numerical_layout.addRow("Trans Sat Penalty:", self.nav_trans_sat_penalty_spin)
        numerical_layout.addRow("Trans Wall Thresh:", self.nav_trans_wall_thresh_spin)
        numerical_layout.addRow("Sat Filter Radius:", self.nav_sat_filter_radius_spin)
        numerical_layout.addRow("Wall Weight:", self.nav_wall_weight_spin)
        numerical_layout.addRow("Edge Weight:", self.nav_edge_weight_spin)
        numerical_layout.addRow("CLAHE Grid:", self.nav_clahe_grid_spin)
        numerical_layout.addRow("Kernel Small Size:", self.nav_kernel_small_spin)
        numerical_layout.addRow("Kernel Medium Size:", self.nav_kernel_medium_spin)
        numerical_layout.addRow("K Ratio (兼容):", self.nav_k_ratio_spin)
        numerical_layout.addRow("Y Bias (兼容):", self.nav_y_bias_spin)

        recognition_layout.addWidget(numerical_group)
        recognition_layout.addStretch(1)

        # ==================== 只读信息区域 ====================
        screen_group = QGroupBox("屏幕点击映射")
        screen_layout = QFormLayout(screen_group)
        obstacle_group = QGroupBox("路径与障碍")
        obstacle_layout = QFormLayout(obstacle_group)
        event_group = QGroupBox("事件靠近/停稳")
        event_form_layout = QFormLayout(event_group)
        runtime_group = QGroupBox("地图与调试")
        runtime_layout = QFormLayout(runtime_group)

        # 角色屏幕坐标显示（只读）
        self.nav_screen_center_x = QLineEdit("N/A")
        self.nav_screen_center_x.setReadOnly(True)
        self.nav_screen_center_y = QLineEdit("N/A")
        self.nav_screen_center_y.setReadOnly(True)

        # 创建水平布局用于并排显示 X/Y 坐标
        screen_center_layout = QHBoxLayout()
        screen_center_layout.addWidget(self.nav_screen_center_x)
        screen_center_layout.addWidget(self.nav_screen_center_y)

        # 运动映射比例调节
        self.nav_movement_scale_factor_spin = QDoubleSpinBox()
        self.nav_movement_scale_factor_spin.setRange(0.1, 10.0)
        self.nav_movement_scale_factor_spin.setSingleStep(0.1)
        self.nav_movement_scale_factor_spin.setDecimals(2)

        self.nav_game_view_map_size_spin = QSpinBox()
        self.nav_game_view_map_size_spin.setRange(100, 3000)
        self.nav_game_view_map_size_spin.setSingleStep(20)

        self.nav_movement_min_click_radius_spin = QSpinBox()
        self.nav_movement_min_click_radius_spin.setRange(0, 2000)
        self.nav_movement_min_click_radius_spin.setSingleStep(10)

        self.nav_movement_max_click_radius_spin = QSpinBox()
        self.nav_movement_max_click_radius_spin.setRange(10, 3000)
        self.nav_movement_max_click_radius_spin.setSingleStep(10)

        self.nav_auto_click_cooldown_spin = QSpinBox()
        self.nav_auto_click_cooldown_spin.setRange(120, 2000)
        self.nav_auto_click_cooldown_spin.setSingleStep(20)
        self.nav_auto_min_target_delta_spin = QDoubleSpinBox()
        self.nav_auto_min_target_delta_spin.setRange(0.0, 100.0)
        self.nav_auto_min_target_delta_spin.setSingleStep(1.0)
        self.nav_auto_min_target_delta_spin.setDecimals(1)

        self.nav_anchor_arrival_radius_spin = QSpinBox()
        self.nav_anchor_arrival_radius_spin.setRange(4, 200)
        self.nav_anchor_arrival_radius_spin.setSingleStep(2)

        self.nav_movement_progress_timeout_spin = QSpinBox()
        self.nav_movement_progress_timeout_spin.setRange(200, 10000)
        self.nav_movement_progress_timeout_spin.setSingleStep(100)

        self.nav_movement_min_progress_delta_spin = QDoubleSpinBox()
        self.nav_movement_min_progress_delta_spin.setRange(0.0, 200.0)
        self.nav_movement_min_progress_delta_spin.setSingleStep(1.0)
        self.nav_movement_min_progress_delta_spin.setDecimals(1)

        self.nav_movement_max_recover_attempts_spin = QSpinBox()
        self.nav_movement_max_recover_attempts_spin.setRange(0, 10)
        self.nav_movement_max_recover_attempts_spin.setSingleStep(1)

        self.nav_movement_path_deviation_threshold_spin = QDoubleSpinBox()
        self.nav_movement_path_deviation_threshold_spin.setRange(8.0, 400.0)
        self.nav_movement_path_deviation_threshold_spin.setSingleStep(4.0)
        self.nav_movement_path_deviation_threshold_spin.setDecimals(1)

        self.nav_event_approach_enabled_chk = QCheckBox("启用事件靠近停稳层")

        self.nav_event_visible_margin_spin = QSpinBox()
        self.nav_event_visible_margin_spin.setRange(0, 500)
        self.nav_event_visible_margin_spin.setSingleStep(5)

        self.nav_event_approach_lookahead_spin = QSpinBox()
        self.nav_event_approach_lookahead_spin.setRange(8, 240)
        self.nav_event_approach_lookahead_spin.setSingleStep(2)

        self.nav_event_approach_click_cooldown_spin = QSpinBox()
        self.nav_event_approach_click_cooldown_spin.setRange(120, 3000)
        self.nav_event_approach_click_cooldown_spin.setSingleStep(50)

        self.nav_event_stop_radius_spin = QSpinBox()
        self.nav_event_stop_radius_spin.setRange(4, 160)
        self.nav_event_stop_radius_spin.setSingleStep(2)

        self.nav_event_settle_ms_spin = QSpinBox()
        self.nav_event_settle_ms_spin.setRange(0, 5000)
        self.nav_event_settle_ms_spin.setSingleStep(100)

        self.nav_event_stable_frames_spin = QSpinBox()
        self.nav_event_stable_frames_spin.setRange(1, 20)
        self.nav_event_stable_frames_spin.setSingleStep(1)

        self.nav_event_max_motion_per_frame_spin = QDoubleSpinBox()
        self.nav_event_max_motion_per_frame_spin.setRange(0.0, 80.0)
        self.nav_event_max_motion_per_frame_spin.setSingleStep(1.0)
        self.nav_event_max_motion_per_frame_spin.setDecimals(1)

        self.nav_bottom_click_guard_spin = QSpinBox()
        self.nav_bottom_click_guard_spin.setRange(0, 1200)
        self.nav_bottom_click_guard_spin.setSingleStep(20)

        self.nav_wall_erode_iterations_spin = QSpinBox()
        self.nav_wall_erode_iterations_spin.setRange(0, 5)
        self.nav_wall_erode_iterations_spin.setSingleStep(1)
        self.nav_path_start_clear_radius_spin = QSpinBox()
        self.nav_path_start_clear_radius_spin.setRange(0, 200)
        self.nav_path_start_clear_radius_spin.setSingleStep(5)
        self.nav_path_walkable_snap_radius_spin = QSpinBox()
        self.nav_path_walkable_snap_radius_spin.setRange(0, 200)
        self.nav_path_walkable_snap_radius_spin.setSingleStep(5)

        self.nav_auto_click_radius_btn = QPushButton("自动估算点击半径")

        # 地图精度显示（只读）
        self.nav_info_draw_scale = QLabel("N/A")

        # 逻辑中心展示（只读）
        self.nav_info_logical_center = QLineEdit("N/A")
        self.nav_info_logical_center.setReadOnly(True)

        # 截图大小展示（只读，必须与建图环境一致）
        self.nav_monitor_size_spin = QSpinBox()
        self.nav_monitor_size_spin.setRange(100, 2000)
        self.nav_monitor_size_spin.setSingleStep(10)
        self.nav_monitor_size_spin.setReadOnly(True)
        self.nav_monitor_size_spin.setButtonSymbols(QSpinBox.NoButtons)

        # FPS 调节
        self.nav_fps_spin = QSpinBox()
        self.nav_fps_spin.setRange(1, 60)
        self.nav_fps_spin.setSingleStep(1)

        self.nav_visual_check_interval_spin = QSpinBox()
        self.nav_visual_check_interval_spin.setRange(0, 10000)
        self.nav_visual_check_interval_spin.setSingleStep(100)

        self.nav_visual_check_margin_spin = QSpinBox()
        self.nav_visual_check_margin_spin.setRange(40, 600)
        self.nav_visual_check_margin_spin.setSingleStep(10)

        self.nav_visual_match_min_conf_spin = QDoubleSpinBox()
        self.nav_visual_match_min_conf_spin.setRange(0.1, 0.99)
        self.nav_visual_match_min_conf_spin.setSingleStep(0.01)
        self.nav_visual_match_min_conf_spin.setDecimals(2)

        self.nav_visual_mismatch_threshold_spin = QDoubleSpinBox()
        self.nav_visual_mismatch_threshold_spin.setRange(4.0, 200.0)
        self.nav_visual_mismatch_threshold_spin.setSingleStep(2.0)
        self.nav_visual_mismatch_threshold_spin.setDecimals(1)

        self.nav_visual_mismatch_frames_spin = QSpinBox()
        self.nav_visual_mismatch_frames_spin.setRange(1, 10)
        self.nav_visual_mismatch_frames_spin.setSingleStep(1)

        # 调试幕布切换按钮
        self.nav_toggle_overlay_btn = QPushButton("切换调试幕布")
        self.nav_toggle_overlay_btn.setCheckable(True)

        # 将控件添加到布局中
        self._add_helpful_row(screen_layout, "角色屏幕坐标 (X/Y)", screen_center_layout, "校准后的游戏人物中心屏幕坐标；点击映射以这里为原点。")
        self._add_helpful_row(screen_layout, "运动映射比例", self.nav_movement_scale_factor_spin, "地图距离换算成屏幕点击距离的倍率；通常只做微调。")
        self._add_helpful_row(screen_layout, "真实可见范围(地图像素)", self.nav_game_view_map_size_spin, "橙色框大小，表示主画面真实可交互视野，不参与定位。")
        self._add_helpful_row(screen_layout, "最小点击半径(屏幕像素)", self.nav_movement_min_click_radius_spin, "点击点距离人物中心的下限，避免点得太近不移动。")
        self._add_helpful_row(screen_layout, "最大点击半径(屏幕像素)", self.nav_movement_max_click_radius_spin, "点击点距离人物中心的上限，避免点到 UI 或视野外。")
        self._add_helpful_row(screen_layout, "自动点击冷却(ms)", self.nav_auto_click_cooldown_spin, "自动导航两次移动点击之间的最小间隔。")
        self._add_helpful_row(screen_layout, "自动点击目标变化阈值", self.nav_auto_min_target_delta_spin, "普通路径中子目标变化小于该值时会抑制重复点击；锚点推进阶段会绕过这个抑制。")
        self._add_helpful_row(screen_layout, "底部禁点区域(px)", self.nav_bottom_click_guard_spin, "屏幕底部禁止点击高度，防止误点技能栏或 UI。")
        screen_layout.addRow(self.nav_auto_click_radius_btn)
        movement_layout.addWidget(screen_group)
        movement_layout.addStretch(1)

        self._add_helpful_row(obstacle_layout, "A* 墙体侵蚀次数", self.nav_wall_erode_iterations_spin, "仅作用于导航障碍层，让视觉墙体变薄、窄通道更容易通过；不改变定位墙体。")
        self._add_helpful_row(obstacle_layout, "A* 起点清空半径(地图像素)", self.nav_path_start_clear_radius_spin, "寻路前清空人物附近障碍，避免定位点贴墙时起点被判进墙。")
        self._add_helpful_row(obstacle_layout, "A* 起终点吸附半径(地图像素)", self.nav_path_walkable_snap_radius_spin, "起点或目标落在障碍附近时，搜索半径内最近可走点。")
        self._add_helpful_row(obstacle_layout, "锚点到达半径(地图像素)", self.nav_anchor_arrival_radius_spin, "距离当前辅助锚点小于该值时认为锚点已消费并切到下一个锚点。")
        self._add_helpful_row(obstacle_layout, "卡住判定间隔(ms)", self.nav_movement_progress_timeout_spin, "在该时间内路径进度不足时触发恢复点击；调小会更快脱困。")
        self._add_helpful_row(obstacle_layout, "最小有效进度(地图像素)", self.nav_movement_min_progress_delta_spin, "卡住判定窗口内至少要前进的路径距离，低于该值认为没有明显移动。")
        self._add_helpful_row(obstacle_layout, "恢复尝试次数", self.nav_movement_max_recover_attempts_spin, "连续卡住时对当前锚点做侧向探测点击的次数，耗尽后强制重规划。")
        self._add_helpful_row(obstacle_layout, "路径偏离阈值(地图像素)", self.nav_movement_path_deviation_threshold_spin, "人物离当前规划路径过远时立即重规划。")
        path_layout.addWidget(obstacle_group)
        path_layout.addStretch(1)

        self._add_helpful_row(event_form_layout, "启用事件停稳层", self.nav_event_approach_enabled_chk, "启用后事件进入真实视野后先近距离收敛并停稳，再交给事件处理器触发。")
        self._add_helpful_row(event_form_layout, "真实视野边距(地图像素)", self.nav_event_visible_margin_spin, "事件点进入橙色真实视野框外加该边距后，切换到近距离靠近逻辑。")
        self._add_helpful_row(event_form_layout, "事件近距离 lookahead", self.nav_event_approach_lookahead_spin, "事件进入真实视野后的 A* 子目标前瞻距离；越小越收敛，越大越快但可能跑过。")
        self._add_helpful_row(event_form_layout, "事件点击冷却(ms)", self.nav_event_approach_click_cooldown_spin, "事件近距离靠近阶段两次移动点击的最小间隔，调大可减少绕点。")
        self._add_helpful_row(event_form_layout, "事件停靠半径(地图像素)", self.nav_event_stop_radius_spin, "人物距离事件前停靠点或事件中心小于该值时停止移动点击，开始等待停稳。")
        self._add_helpful_row(event_form_layout, "停稳等待(ms)", self.nav_event_settle_ms_spin, "到达事件附近后等待多久再允许事件处理器点击或按键。")
        self._add_helpful_row(event_form_layout, "停稳帧数", self.nav_event_stable_frames_spin, "连续多少帧位移足够小才认为角色已停稳。")
        self._add_helpful_row(event_form_layout, "停稳最大位移/帧", self.nav_event_max_motion_per_frame_spin, "停稳判断中每帧允许的最大地图位移，过小会等待更久。")
        event_layout.addWidget(event_group)
        event_layout.addStretch(1)

        self._add_helpful_row(runtime_layout, "地图精度 (Draw Scale)", self.nav_info_draw_scale, "当前地图绘制缩放，只读；必须与建图数据一致。")
        self._add_helpful_row(runtime_layout, "逻辑中心 (建图继承)", self.nav_info_logical_center, "小地图截图区域，只读；定位必须与建图环境一致。")
        self._add_helpful_row(runtime_layout, "截图大小 (建图继承)", self.nav_monitor_size_spin, "定位监视窗口大小，只读；来自建图配置。")
        self._add_helpful_row(runtime_layout, "导航刷新率 (FPS)", self.nav_fps_spin, "导航循环刷新率；过高会增加 CPU 和点击判断频率。")
        self._add_helpful_row(runtime_layout, "视觉校验间隔(ms)", self.nav_visual_check_interval_spin, "F2F 跟踪时隔多久用当前截图在大地图附近做一次模板校验；0 表示关闭自动视觉校验。")
        self._add_helpful_row(runtime_layout, "视觉校验搜索边距", self.nav_visual_check_margin_spin, "围绕当前人物位置的模板搜索边距，越大越能发现偏移但越耗 CPU。")
        self._add_helpful_row(runtime_layout, "视觉校验最低置信度", self.nav_visual_match_min_conf_spin, "截图贴回大地图的局部匹配分数低于该值时，不把偏移当作有效证据。")
        self._add_helpful_row(runtime_layout, "视觉偏移阈值(地图像素)", self.nav_visual_mismatch_threshold_spin, "截图最佳贴图位置与当前导航人物点的距离超过该值，才算一次视觉偏移。")
        self._add_helpful_row(runtime_layout, "视觉偏移连续帧数", self.nav_visual_mismatch_frames_spin, "连续多少次视觉校验都偏移，才触发一次强制重定位。")
        runtime_layout.addRow(self.nav_toggle_overlay_btn)
        map_layout.addWidget(runtime_group)
        map_layout.addStretch(1)

        self._apply_parameter_help()

        # ==================== 动作和状态区域 ====================
        # 创建底部动作栏，包含保存按钮和状态标签
        action_layout = QHBoxLayout()
        self.nav_save_btn = QPushButton("保存当前导航参数")
        self.nav_save_default_btn = QPushButton("保存为默认配置")
        self.nav_status_label = QLabel("参数未加载")
        # 状态标签右对齐
        self.nav_status_label.setAlignment(Qt.AlignRight)

        action_layout.addWidget(self.nav_save_btn)
        action_layout.addWidget(self.nav_save_default_btn)
        # 状态标签使用拉伸因子占据剩余空间
        action_layout.addWidget(self.nav_status_label, 1)

        dialog_layout.addLayout(action_layout)

    def _add_helpful_row(self, layout: QFormLayout, label: str, widget, help_text: str):
        label_widget = QLabel(f"{label}\n{help_text}")
        label_widget.setWordWrap(True)
        label_widget.setToolTip(help_text)
        label_widget.setStyleSheet("QLabel { color: #3f3f3f; }")
        if hasattr(widget, "setToolTip"):
            widget.setToolTip(help_text)
        layout.addRow(label_widget, widget)

    def _apply_parameter_help(self):
        help_map = {
            self.nav_wall_hsv_min_edit: "墙体颜色 HSV 下限，影响墙体识别。",
            self.nav_wall_hsv_max_edit: "墙体颜色 HSV 上限，影响墙体识别。",
            self.nav_fog_hsv_min_edit: "迷雾颜色 HSV 下限，影响未探索区域识别。",
            self.nav_fog_hsv_max_edit: "迷雾颜色 HSV 上限，影响未探索区域识别。",
            self.nav_player_hsv_min_edit: "玩家图标 HSV 下限，影响人物定位。",
            self.nav_player_hsv_max_edit: "玩家图标 HSV 上限，影响人物定位。",
            self.nav_chk_enable_wall: "启用后识别墙体并参与建图/导航障碍处理。",
            self.nav_chk_enable_fog: "启用后识别迷雾或未探索区域。",
            self.nav_chk_clahe_enabled: "增强小地图局部对比度，过高可能放大噪声。",
            self.nav_chk_deepen_enabled: "加深颜色差异，便于分离地图要素。",
            self.nav_chk_gamma_enabled: "调整亮度曲线，适合小地图偏暗或偏亮时使用。",
            self.nav_chk_tophat_enabled: "突出小地图细小高亮结构。",
            self.nav_chk_sat_filter_enabled: "按饱和度过滤噪声或 UI 干扰。",
            self.nav_chk_transparent_mode: "用于透明小地图或低对比度地图的特殊墙体判定。",
            self.nav_clahe_clip_spin: "CLAHE 对比度限制，越高增强越强。",
            self.nav_deepen_factor_spin: "颜色深化倍率，影响墙体和背景分离。",
            self.nav_gamma_value_spin: "Gamma 校正值，影响亮度曲线。",
            self.nav_tophat_strength_spin: "顶帽结果叠加强度，影响细节突出程度。",
            self.nav_tophat_kernel_size_spin: "顶帽形态学核大小，需为奇数更稳定。",
            self.nav_sat_filter_thresh_spin: "饱和度过滤阈值，低饱和区域会被压制。",
            self.nav_edge_low_spin: "Canny 边缘低阈值。",
            self.nav_edge_high_spin: "Canny 边缘高阈值。",
            self.nav_blue_boost_spin: "蓝色通道增强倍率。",
            self.nav_trans_sat_penalty_spin: "透明模式下低饱和区域惩罚强度。",
            self.nav_trans_wall_thresh_spin: "透明模式墙体判定阈值。",
            self.nav_sat_filter_radius_spin: "饱和度过滤的局部半径。",
            self.nav_wall_weight_spin: "墙体颜色结果权重。",
            self.nav_edge_weight_spin: "边缘检测结果权重。",
            self.nav_clahe_grid_spin: "CLAHE 分块网格大小。",
            self.nav_kernel_small_spin: "小形态学核大小，用于轻量开闭运算。",
            self.nav_kernel_medium_spin: "中形态学核大小，用于更强的连通/去噪。",
            self.nav_k_ratio_spin: "兼容旧配置，不作为当前定位修正依据。",
            self.nav_y_bias_spin: "兼容旧配置，不作为当前定位修正依据。",
            self.nav_event_approach_enabled_chk: "事件近距离靠近和停稳门控的总开关。",
            self.nav_event_visible_margin_spin: "真实视野框额外边距，影响事件从远距离导航切入近距离收敛的时机。",
            self.nav_event_approach_lookahead_spin: "事件近距离阶段的路径前瞻距离。",
            self.nav_event_approach_click_cooldown_spin: "事件近距离阶段的点击节流。",
            self.nav_event_stop_radius_spin: "事件触发前停止移动点击的半径。",
            self.nav_event_settle_ms_spin: "事件触发前等待停稳的时间。",
            self.nav_event_stable_frames_spin: "事件触发前要求的连续稳定帧数。",
            self.nav_event_max_motion_per_frame_spin: "事件停稳判定允许的最大单帧位移。",
        }
        for widget, help_text in help_map.items():
            widget.setToolTip(help_text)

    def _connect_signals(self):
        """
        连接所有输入控件的信号到处理槽

        使用 `functools.partial` 为每个控件创建一个定制化的处理函数，
        该函数知道要更新配置对象中的哪个具体属性。
        这种方法避免了从 UI 完全重建配置的需要，确保了参数的精确更新。
        """
        if self._signals_connected:
            return

        # 定义 UI 控件与 NavConfig 属性之间的映射
        # 格式: {widget: (sub_config_name, attribute_name)}
        widget_map = {
            # RecognizerParams - Booleans
            self.nav_chk_enable_wall: ("recognizer_params", "enable_wall"),
            self.nav_chk_enable_fog: ("recognizer_params", "enable_fog"),
            self.nav_chk_clahe_enabled: ("recognizer_params", "clahe_enabled"),
            self.nav_chk_deepen_enabled: ("recognizer_params", "deepen_enabled"),
            self.nav_chk_gamma_enabled: ("recognizer_params", "gamma_enabled"),
            self.nav_chk_tophat_enabled: ("recognizer_params", "tophat_enabled"),
            self.nav_chk_sat_filter_enabled: ("recognizer_params", "sat_filter_enabled"),
            self.nav_chk_transparent_mode: ("recognizer_params", "transparent_mode"),
            # RecognizerParams - Numerics
            self.nav_clahe_clip_spin: ("recognizer_params", "clahe_clip"),
            self.nav_deepen_factor_spin: ("recognizer_params", "deepen_factor"),
            self.nav_gamma_value_spin: ("recognizer_params", "gamma_value"),
            self.nav_tophat_strength_spin: ("recognizer_params", "tophat_strength"),
            self.nav_tophat_kernel_size_spin: ("recognizer_params", "tophat_kernel_size"),
            self.nav_sat_filter_thresh_spin: ("recognizer_params", "sat_filter_thresh"),
            self.nav_edge_low_spin: ("recognizer_params", "edge_low"),
            self.nav_edge_high_spin: ("recognizer_params", "edge_high"),
            self.nav_blue_boost_spin: ("recognizer_params", "blue_boost"),
            self.nav_trans_sat_penalty_spin: ("recognizer_params", "trans_sat_penalty"),
            self.nav_trans_wall_thresh_spin: ("recognizer_params", "trans_wall_thresh"),
            self.nav_sat_filter_radius_spin: ("recognizer_params", "sat_filter_radius"),
            self.nav_wall_weight_spin: ("recognizer_params", "wall_weight"),
            self.nav_edge_weight_spin: ("recognizer_params", "edge_weight"),
            self.nav_clahe_grid_spin: ("recognizer_params", "clahe_grid"),
            self.nav_kernel_small_spin: ("recognizer_params", "kernel_small_size"),
            self.nav_kernel_medium_spin: ("recognizer_params", "kernel_medium_size"),
            # NavPreferences
            self.nav_k_ratio_spin: ("nav_preferences", "k_ratio"),
            self.nav_y_bias_spin: ("nav_preferences", "y_bias"),
            # NavConfig root
            self.nav_movement_scale_factor_spin: (None, "movement_scale_factor"),
            self.nav_game_view_map_size_spin: (None, "game_view_map_size"),
            self.nav_movement_min_click_radius_spin: (None, "movement_min_click_radius"),
            self.nav_movement_max_click_radius_spin: (None, "movement_max_click_radius"),
            self.nav_auto_click_cooldown_spin: (None, "auto_click_cooldown_ms"),
            self.nav_auto_min_target_delta_spin: (None, "auto_min_click_target_delta"),
            self.nav_anchor_arrival_radius_spin: (None, "anchor_arrival_radius"),
            self.nav_movement_progress_timeout_spin: (None, "movement_progress_timeout_ms"),
            self.nav_movement_min_progress_delta_spin: (None, "movement_min_progress_delta"),
            self.nav_movement_max_recover_attempts_spin: (None, "movement_max_recover_attempts"),
            self.nav_movement_path_deviation_threshold_spin: (None, "movement_path_deviation_threshold"),
            self.nav_event_approach_enabled_chk: (None, "event_approach_enabled"),
            self.nav_event_visible_margin_spin: (None, "event_visible_margin"),
            self.nav_event_approach_lookahead_spin: (None, "event_approach_lookahead"),
            self.nav_event_approach_click_cooldown_spin: (None, "event_approach_click_cooldown_ms"),
            self.nav_event_stop_radius_spin: (None, "event_stop_radius"),
            self.nav_event_settle_ms_spin: (None, "event_settle_ms"),
            self.nav_event_stable_frames_spin: (None, "event_stable_frames"),
            self.nav_event_max_motion_per_frame_spin: (None, "event_max_motion_per_frame"),
            self.nav_bottom_click_guard_spin: (None, "bottom_click_guard_pixels"),
            self.nav_wall_erode_iterations_spin: (None, "nav_wall_erode_iterations"),
            self.nav_path_start_clear_radius_spin: (None, "path_start_clear_radius"),
            self.nav_path_walkable_snap_radius_spin: (None, "path_walkable_snap_radius"),
            self.nav_visual_check_interval_spin: (None, "coordinate_visual_check_interval_ms"),
            self.nav_visual_check_margin_spin: (None, "coordinate_visual_check_margin"),
            self.nav_visual_match_min_conf_spin: (None, "coordinate_visual_match_min_confidence"),
            self.nav_visual_mismatch_threshold_spin: (None, "coordinate_visual_mismatch_threshold"),
            self.nav_visual_mismatch_frames_spin: (None, "coordinate_visual_mismatch_frames"),
            self.nav_fps_spin: (None, "fps"),
        }

        # 遍历映射，为 QSpinBox, QDoubleSpinBox, QCheckBox 连接 valueChanged/stateChanged 信号
        for widget, (sub_config, attr) in widget_map.items():
            if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                handler = functools.partial(self._update_config_value, sub_config, attr)
                widget.valueChanged.connect(handler)
            elif isinstance(widget, QCheckBox):
                # QCheckBox 的 stateChanged 信号发送的是 Qt.CheckState 枚举，需要转换为布尔值
                handler = functools.partial(self._update_config_value, sub_config, attr, to_bool=True)
                widget.stateChanged.connect(handler)

        # 为 QLineEdit 连接 textChanged 信号，使用单独的处理函数
        text_widget_map = {
            self.nav_wall_hsv_min_edit: ("recognizer_params", "wall_hsv_min"),
            self.nav_wall_hsv_max_edit: ("recognizer_params", "wall_hsv_max"),
            self.nav_fog_hsv_min_edit: ("recognizer_params", "fog_hsv_min"),
            self.nav_fog_hsv_max_edit: ("recognizer_params", "fog_hsv_max"),
            self.nav_player_hsv_min_edit: ("recognizer_params", "player_hsv_min"),
            self.nav_player_hsv_max_edit: ("recognizer_params", "player_hsv_max"),
        }
        for widget, (sub_config, attr) in text_widget_map.items():
            handler = functools.partial(self._update_config_text_value, sub_config, attr)
            widget.textChanged.connect(handler)

        # Action buttons are not disconnected by set_config_to_ui(), so connect them once.
        if not self._action_buttons_connected:
            self.nav_save_btn.clicked.connect(self.save_requested)
            self.nav_save_default_btn.clicked.connect(self.save_default_requested)
            self.nav_auto_click_radius_btn.clicked.connect(self._auto_estimate_click_radius)
            self._action_buttons_connected = True
        self._signals_connected = True

    def _update_config_value(self, sub_config_name: str | None, attr_name: str, value, to_bool: bool = False):
        """通用配置更新槽，用于处理数值和布尔类型的参数更新"""
        if self.config is None:
            return

        if to_bool:
            value = bool(value)

        target_obj = self.config
        if sub_config_name:
            target_obj = getattr(self.config, sub_config_name)

        # 使用 dataclasses.replace 创建新实例，以保持不变性
        new_sub_config = dataclasses.replace(target_obj, **{attr_name: value})

        if sub_config_name:
            self.config = dataclasses.replace(self.config, **{sub_config_name: new_sub_config})
        else:
            self.config = new_sub_config

        self.parameters_changed.emit(self.config)
        self.nav_status_label.setText("有未保存的修改")

    def _update_config_text_value(self, sub_config_name: str | None, attr_name: str, text: str):
        """专门用于处理文本输入框的配置更新槽"""
        if self.config is None:
            return

        try:
            # ast.literal_eval 比 eval 更安全
            value = ast.literal_eval(text)
        except (ValueError, SyntaxError):
            # 如果输入不是有效的 Python 字面量（例如，不完整的列表），则不更新
            return

        self._update_config_value(sub_config_name, attr_name, value)

    def _screen_physical_bounds_for_center(self, center):
        """Find physical screen bounds containing a calibrated physical center."""
        if not center:
            return None

        cx, cy = int(center[0]), int(center[1])
        screens = QApplication.screens() or [QApplication.primaryScreen()]
        fallback = None
        for screen in screens:
            if screen is None:
                continue
            dpr = screen.devicePixelRatio() or 1.0
            geometry = screen.geometry()
            left = int(round(geometry.x() * dpr))
            top = int(round(geometry.y() * dpr))
            right = left + int(round(geometry.width() * dpr))
            bottom = top + int(round(geometry.height() * dpr))
            bounds = (left, top, right, bottom)
            fallback = fallback or bounds
            if left <= cx <= right and top <= cy <= bottom:
                return bounds
        return fallback

    def _auto_estimate_click_radius(self):
        """Estimate click radii from calibrated center and physical screen size."""
        if self.config is None:
            return
        if not self.config.game_screen_center:
            self.nav_status_label.setText("请先校准屏幕中心")
            return

        bounds = self._screen_physical_bounds_for_center(self.config.game_screen_center)
        if not bounds:
            self.nav_status_label.setText("无法读取屏幕尺寸")
            return

        cx, cy = self.config.game_screen_center
        left, top, right, bottom = bounds
        safe_radius = min(cx - left, right - cx, cy - top, bottom - cy)
        if safe_radius <= 0:
            self.nav_status_label.setText("屏幕中心不在当前屏幕范围内")
            return

        max_radius = max(180, min(900, int(safe_radius * 0.70)))
        min_radius = max(120, int(max_radius * 0.55))

        self.nav_movement_min_click_radius_spin.setValue(min_radius)
        self.nav_movement_max_click_radius_spin.setValue(max_radius)
        self.nav_status_label.setText(
            f"已估算点击半径: {min_radius}-{max_radius}px"
        )


    def set_config_to_ui(self, config: NavConfig, physical_center: tuple):
        """
        使用 NavConfig 对象的内容更新 UI 面板

        该方法会将配置对象中的所有参数值填充到对应的 UI 控件中，
        并将其保存在 self.config 中。
        为了避免在更新 UI 时触发信号处理，会先断开所有信号连接，
        更新完成后再重新连接。

        参数:
            config (NavConfig): 包含导航配置数据的对象
            physical_center (tuple): 物理中心坐标（当前未使用，保留用于兼容性）

        注意:
            该方法会临时断开所有信号连接以避免循环触发，
            更新完成后会自动重新连接信号。
        """
        # 核心步骤：保存传入的配置对象，使对话框有状态
        self.config = config

        # Block control signals while programmatically writing values into the panel.
        signal_blockers = [QSignalBlocker(w) for w in self.findChildren(QWidget)]

        # ==================== 从配置对象更新 UI ====================
        prefs = config.nav_preferences
        rec_params = config.recognizer_params

        # 更新 HSV 范围输入框
        self.nav_wall_hsv_min_edit.setText(str(rec_params.wall_hsv_min))
        self.nav_wall_hsv_max_edit.setText(str(rec_params.wall_hsv_max))
        self.nav_fog_hsv_min_edit.setText(str(rec_params.fog_hsv_min))
        self.nav_fog_hsv_max_edit.setText(str(rec_params.fog_hsv_max))
        self.nav_player_hsv_min_edit.setText(str(rec_params.player_hsv_min))
        self.nav_player_hsv_max_edit.setText(str(rec_params.player_hsv_max))

        # 更新算法开关复选框
        self.nav_chk_enable_wall.setChecked(rec_params.enable_wall)
        self.nav_chk_enable_fog.setChecked(rec_params.enable_fog)
        self.nav_chk_clahe_enabled.setChecked(rec_params.clahe_enabled)
        self.nav_chk_deepen_enabled.setChecked(rec_params.deepen_enabled)
        self.nav_chk_gamma_enabled.setChecked(rec_params.gamma_enabled)
        self.nav_chk_tophat_enabled.setChecked(rec_params.tophat_enabled)
        self.nav_chk_sat_filter_enabled.setChecked(rec_params.sat_filter_enabled)
        self.nav_chk_transparent_mode.setChecked(rec_params.transparent_mode)

        # 更新算法数值
        self.nav_clahe_clip_spin.setValue(rec_params.clahe_clip)
        self.nav_deepen_factor_spin.setValue(rec_params.deepen_factor)
        self.nav_gamma_value_spin.setValue(rec_params.gamma_value)
        self.nav_tophat_strength_spin.setValue(rec_params.tophat_strength)
        self.nav_tophat_kernel_size_spin.setValue(rec_params.tophat_kernel_size)
        self.nav_sat_filter_thresh_spin.setValue(rec_params.sat_filter_thresh)
        self.nav_edge_low_spin.setValue(rec_params.edge_low)
        self.nav_edge_high_spin.setValue(rec_params.edge_high)
        self.nav_blue_boost_spin.setValue(rec_params.blue_boost)
        self.nav_trans_sat_penalty_spin.setValue(rec_params.trans_sat_penalty)
        self.nav_trans_wall_thresh_spin.setValue(rec_params.trans_wall_thresh)
        self.nav_sat_filter_radius_spin.setValue(rec_params.sat_filter_radius)
        self.nav_wall_weight_spin.setValue(rec_params.wall_weight)
        self.nav_edge_weight_spin.setValue(rec_params.edge_weight)
        self.nav_clahe_grid_spin.setValue(rec_params.clahe_grid)
        self.nav_kernel_small_spin.setValue(rec_params.kernel_small_size)
        self.nav_kernel_medium_spin.setValue(rec_params.kernel_medium_size)

        # 更新地图与运动控制
        self.nav_info_draw_scale.setText(str(config.draw_scale))
        if config.monitor_region:
            region = config.monitor_region
            self.nav_info_logical_center.setText(
                f"拉框区域: ({region['left']}, {region['top']}) {region['width']}x{region['height']}"
            )
        else:
            self.nav_info_logical_center.setText(str(config.monitor_logical_center))
        self.nav_monitor_size_spin.setValue(config.monitor_size)
        self.nav_movement_scale_factor_spin.setValue(config.movement_scale_factor)
        self.nav_game_view_map_size_spin.setValue(config.game_view_map_size)
        self.nav_movement_min_click_radius_spin.setValue(config.movement_min_click_radius)
        self.nav_movement_max_click_radius_spin.setValue(config.movement_max_click_radius)
        self.nav_auto_click_cooldown_spin.setValue(config.auto_click_cooldown_ms)
        self.nav_auto_min_target_delta_spin.setValue(config.auto_min_click_target_delta)
        self.nav_anchor_arrival_radius_spin.setValue(config.anchor_arrival_radius)
        self.nav_movement_progress_timeout_spin.setValue(config.movement_progress_timeout_ms)
        self.nav_movement_min_progress_delta_spin.setValue(config.movement_min_progress_delta)
        self.nav_movement_max_recover_attempts_spin.setValue(config.movement_max_recover_attempts)
        self.nav_movement_path_deviation_threshold_spin.setValue(config.movement_path_deviation_threshold)
        self.nav_event_approach_enabled_chk.setChecked(config.event_approach_enabled)
        self.nav_event_visible_margin_spin.setValue(config.event_visible_margin)
        self.nav_event_approach_lookahead_spin.setValue(config.event_approach_lookahead)
        self.nav_event_approach_click_cooldown_spin.setValue(config.event_approach_click_cooldown_ms)
        self.nav_event_stop_radius_spin.setValue(config.event_stop_radius)
        self.nav_event_settle_ms_spin.setValue(config.event_settle_ms)
        self.nav_event_stable_frames_spin.setValue(config.event_stable_frames)
        self.nav_event_max_motion_per_frame_spin.setValue(config.event_max_motion_per_frame)
        self.nav_bottom_click_guard_spin.setValue(config.bottom_click_guard_pixels)
        self.nav_wall_erode_iterations_spin.setValue(config.nav_wall_erode_iterations)
        self.nav_path_start_clear_radius_spin.setValue(config.path_start_clear_radius)
        self.nav_path_walkable_snap_radius_spin.setValue(config.path_walkable_snap_radius)
        self.nav_visual_check_interval_spin.setValue(config.coordinate_visual_check_interval_ms)
        self.nav_visual_check_margin_spin.setValue(config.coordinate_visual_check_margin)
        self.nav_visual_match_min_conf_spin.setValue(config.coordinate_visual_match_min_confidence)
        self.nav_visual_mismatch_threshold_spin.setValue(config.coordinate_visual_mismatch_threshold)
        self.nav_visual_mismatch_frames_spin.setValue(config.coordinate_visual_mismatch_frames)

        # 更新角色屏幕坐标显示
        if config.game_screen_center:
            self.nav_screen_center_x.setText(str(config.game_screen_center[0]))
            self.nav_screen_center_y.setText(str(config.game_screen_center[1]))
        else:
            self.nav_screen_center_x.setText("N/A")
            self.nav_screen_center_y.setText("N/A")

        # 更新新增的UI控件
        self.nav_fps_spin.setValue(config.fps)
        self.nav_k_ratio_spin.setValue(prefs.k_ratio)
        self.nav_y_bias_spin.setValue(prefs.y_bias)

        # 更新状态标签
        self.nav_status_label.setText("参数已加载")

        # ==================== 重新连接信号 ====================
        self._connect_signals()
