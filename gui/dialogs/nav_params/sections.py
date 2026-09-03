from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
)

from .layout_helpers import create_scrollable_tab


def build_navigation_parameter_tabs(dialog, nav_tabs: QTabWidget) -> None:
    """Build all navigation parameter tabs and write widgets back to the dialog."""
    positioning_tab, positioning_layout = create_scrollable_tab()
    recognition_tab, recognition_layout = create_scrollable_tab()
    movement_tab, movement_layout = create_scrollable_tab()
    path_tab, path_layout = create_scrollable_tab()
    event_tab, event_layout = create_scrollable_tab()
    map_tab, map_layout = create_scrollable_tab()

    nav_tabs.addTab(positioning_tab, "定位识别")
    nav_tabs.addTab(recognition_tab, "识别算法")
    nav_tabs.addTab(movement_tab, "移动点击")
    nav_tabs.addTab(path_tab, "路径/A*")
    nav_tabs.addTab(event_tab, "事件靠近")
    nav_tabs.addTab(map_tab, "地图/调试")

    build_positioning_sections(dialog, positioning_layout)
    build_recognition_sections(dialog, recognition_layout)
    build_movement_section(dialog, movement_layout)
    build_path_section(dialog, path_layout)
    build_event_section(dialog, event_layout)
    build_map_debug_section(dialog, map_layout)
    apply_parameter_help(dialog)


def build_action_bar(dialog) -> QHBoxLayout:
    """Build the footer actions for the navigation parameter dialog."""
    action_layout = QHBoxLayout()
    dialog.nav_compact_mode_btn = QPushButton("完整模式")
    dialog.nav_save_btn = QPushButton("保存当前导航参数")
    dialog.nav_save_default_btn = QPushButton("保存为默认配置")
    dialog.nav_status_label = QLabel("参数未加载")
    dialog.nav_status_label.setAlignment(Qt.AlignRight)

    action_layout.addWidget(dialog.nav_compact_mode_btn)
    action_layout.addWidget(dialog.nav_save_btn)
    action_layout.addWidget(dialog.nav_save_default_btn)
    action_layout.addWidget(dialog.nav_status_label, 1)
    return action_layout


def build_positioning_sections(dialog, positioning_layout) -> None:
    hsv_group = QGroupBox("识别参数")
    hsv_layout = QFormLayout(hsv_group)

    dialog.nav_wall_hsv_min_edit = QLineEdit()
    dialog.nav_wall_hsv_max_edit = QLineEdit()
    dialog.nav_fog_hsv_min_edit = QLineEdit()
    dialog.nav_fog_hsv_max_edit = QLineEdit()
    dialog.nav_player_hsv_min_edit = QLineEdit()
    dialog.nav_player_hsv_max_edit = QLineEdit()

    hsv_layout.addRow("墙体 HSV Min:", dialog.nav_wall_hsv_min_edit)
    hsv_layout.addRow("墙体 HSV Max:", dialog.nav_wall_hsv_max_edit)
    hsv_layout.addRow("迷雾 HSV Min:", dialog.nav_fog_hsv_min_edit)
    hsv_layout.addRow("迷雾 HSV Max:", dialog.nav_fog_hsv_max_edit)
    hsv_layout.addRow("玩家 HSV Min:", dialog.nav_player_hsv_min_edit)
    hsv_layout.addRow("玩家 HSV Max:", dialog.nav_player_hsv_max_edit)
    positioning_layout.addWidget(hsv_group)

    flags_group = QGroupBox("算法开关 (Flags)")
    flags_layout = QGridLayout(flags_group)

    dialog.nav_chk_enable_wall = QCheckBox("启用墙体识别")
    dialog.nav_chk_enable_fog = QCheckBox("启用迷雾识别")
    dialog.nav_chk_clahe_enabled = QCheckBox("启用 CLAHE")
    dialog.nav_chk_deepen_enabled = QCheckBox("启用颜色深化")
    dialog.nav_chk_gamma_enabled = QCheckBox("启用 Gamma 校正")
    dialog.nav_chk_tophat_enabled = QCheckBox("启用顶帽变换")
    dialog.nav_chk_sat_filter_enabled = QCheckBox("启用饱和度过滤")
    dialog.nav_chk_transparent_mode = QCheckBox("启用透明模式")

    flags_layout.addWidget(dialog.nav_chk_enable_wall, 0, 0)
    flags_layout.addWidget(dialog.nav_chk_enable_fog, 0, 1)
    flags_layout.addWidget(dialog.nav_chk_clahe_enabled, 1, 0)
    flags_layout.addWidget(dialog.nav_chk_deepen_enabled, 1, 1)
    flags_layout.addWidget(dialog.nav_chk_gamma_enabled, 2, 0)
    flags_layout.addWidget(dialog.nav_chk_tophat_enabled, 2, 1)
    flags_layout.addWidget(dialog.nav_chk_sat_filter_enabled, 3, 0)
    flags_layout.addWidget(dialog.nav_chk_transparent_mode, 3, 1)

    positioning_layout.addWidget(flags_group)
    positioning_layout.addStretch(1)


def build_recognition_sections(dialog, recognition_layout) -> None:
    numerical_group = QGroupBox("算法数值 (Values)")
    numerical_layout = QFormLayout(numerical_group)

    dialog.nav_clahe_clip_spin = QDoubleSpinBox()
    dialog.nav_clahe_clip_spin.setRange(1.0, 10.0)
    dialog.nav_clahe_clip_spin.setSingleStep(0.5)

    dialog.nav_deepen_factor_spin = QDoubleSpinBox()
    dialog.nav_deepen_factor_spin.setRange(0.1, 2.0)
    dialog.nav_deepen_factor_spin.setSingleStep(0.1)

    dialog.nav_gamma_value_spin = QDoubleSpinBox()
    dialog.nav_gamma_value_spin.setRange(0.1, 5.0)
    dialog.nav_gamma_value_spin.setSingleStep(0.1)

    dialog.nav_tophat_strength_spin = QDoubleSpinBox()
    dialog.nav_tophat_strength_spin.setRange(0.0, 10.0)
    dialog.nav_tophat_strength_spin.setSingleStep(0.5)

    dialog.nav_tophat_kernel_size_spin = QSpinBox()
    dialog.nav_tophat_kernel_size_spin.setRange(1, 31)
    dialog.nav_tophat_kernel_size_spin.setSingleStep(2)

    dialog.nav_sat_filter_thresh_spin = QSpinBox()
    dialog.nav_sat_filter_thresh_spin.setRange(0, 255)
    dialog.nav_sat_filter_thresh_spin.setSingleStep(5)

    dialog.nav_edge_low_spin = QSpinBox()
    dialog.nav_edge_low_spin.setRange(0, 255)
    dialog.nav_edge_low_spin.setSingleStep(5)

    dialog.nav_edge_high_spin = QSpinBox()
    dialog.nav_edge_high_spin.setRange(0, 255)
    dialog.nav_edge_high_spin.setSingleStep(5)

    dialog.nav_blue_boost_spin = QDoubleSpinBox()
    dialog.nav_blue_boost_spin.setRange(0.1, 3.0)
    dialog.nav_blue_boost_spin.setSingleStep(0.1)

    dialog.nav_trans_sat_penalty_spin = QDoubleSpinBox()
    dialog.nav_trans_sat_penalty_spin.setRange(0.0, 5.0)
    dialog.nav_trans_sat_penalty_spin.setSingleStep(0.1)

    dialog.nav_trans_wall_thresh_spin = QSpinBox()
    dialog.nav_trans_wall_thresh_spin.setRange(0, 255)
    dialog.nav_trans_wall_thresh_spin.setSingleStep(1)

    dialog.nav_sat_filter_radius_spin = QSpinBox()
    dialog.nav_sat_filter_radius_spin.setRange(0, 100)
    dialog.nav_sat_filter_radius_spin.setSingleStep(5)

    dialog.nav_wall_weight_spin = QSpinBox()
    dialog.nav_wall_weight_spin.setRange(0, 100)
    dialog.nav_wall_weight_spin.setSingleStep(5)

    dialog.nav_edge_weight_spin = QSpinBox()
    dialog.nav_edge_weight_spin.setRange(0, 100)
    dialog.nav_edge_weight_spin.setSingleStep(5)

    dialog.nav_clahe_grid_spin = QSpinBox()
    dialog.nav_clahe_grid_spin.setRange(2, 16)
    dialog.nav_clahe_grid_spin.setSingleStep(1)

    dialog.nav_kernel_small_spin = QSpinBox()
    dialog.nav_kernel_small_spin.setRange(1, 15)
    dialog.nav_kernel_small_spin.setSingleStep(2)

    dialog.nav_kernel_medium_spin = QSpinBox()
    dialog.nav_kernel_medium_spin.setRange(1, 15)
    dialog.nav_kernel_medium_spin.setSingleStep(2)

    numerical_layout.addRow("CLAHE Clip:", dialog.nav_clahe_clip_spin)
    numerical_layout.addRow("Deepen Factor:", dialog.nav_deepen_factor_spin)
    numerical_layout.addRow("Gamma Value:", dialog.nav_gamma_value_spin)
    numerical_layout.addRow("TopHat Strength:", dialog.nav_tophat_strength_spin)
    numerical_layout.addRow("TopHat Kernel Size:", dialog.nav_tophat_kernel_size_spin)
    numerical_layout.addRow("Sat Filter Thresh:", dialog.nav_sat_filter_thresh_spin)
    numerical_layout.addRow("Canny Low:", dialog.nav_edge_low_spin)
    numerical_layout.addRow("Canny High:", dialog.nav_edge_high_spin)
    numerical_layout.addRow("Blue Boost:", dialog.nav_blue_boost_spin)
    numerical_layout.addRow("Trans Sat Penalty:", dialog.nav_trans_sat_penalty_spin)
    numerical_layout.addRow("Trans Wall Thresh:", dialog.nav_trans_wall_thresh_spin)
    numerical_layout.addRow("Sat Filter Radius:", dialog.nav_sat_filter_radius_spin)
    numerical_layout.addRow("Wall Weight:", dialog.nav_wall_weight_spin)
    numerical_layout.addRow("Edge Weight:", dialog.nav_edge_weight_spin)
    numerical_layout.addRow("CLAHE Grid:", dialog.nav_clahe_grid_spin)
    numerical_layout.addRow("Kernel Small Size:", dialog.nav_kernel_small_spin)
    numerical_layout.addRow("Kernel Medium Size:", dialog.nav_kernel_medium_spin)

    recognition_layout.addWidget(numerical_group)
    recognition_layout.addStretch(1)


def build_movement_section(dialog, movement_layout) -> None:
    screen_group = QGroupBox("屏幕点击映射")
    screen_layout = QFormLayout(screen_group)

    dialog.nav_screen_center_x = QLineEdit("N/A")
    dialog.nav_screen_center_x.setReadOnly(True)
    dialog.nav_screen_center_y = QLineEdit("N/A")
    dialog.nav_screen_center_y.setReadOnly(True)

    screen_center_layout = QHBoxLayout()
    screen_center_layout.addWidget(dialog.nav_screen_center_x)
    screen_center_layout.addWidget(dialog.nav_screen_center_y)

    dialog.nav_movement_scale_factor_spin = QDoubleSpinBox()
    dialog.nav_movement_scale_factor_spin.setRange(0.1, 10.0)
    dialog.nav_movement_scale_factor_spin.setSingleStep(0.1)
    dialog.nav_movement_scale_factor_spin.setDecimals(2)

    dialog.nav_game_view_map_size_spin = QSpinBox()
    dialog.nav_game_view_map_size_spin.setRange(100, 3000)
    dialog.nav_game_view_map_size_spin.setSingleStep(20)

    dialog.nav_movement_min_click_radius_spin = QSpinBox()
    dialog.nav_movement_min_click_radius_spin.setRange(0, 2000)
    dialog.nav_movement_min_click_radius_spin.setSingleStep(10)

    dialog.nav_movement_max_click_radius_spin = QSpinBox()
    dialog.nav_movement_max_click_radius_spin.setRange(10, 3000)
    dialog.nav_movement_max_click_radius_spin.setSingleStep(10)

    dialog.nav_movement_precision_click_max_radius_spin = QSpinBox()
    dialog.nav_movement_precision_click_max_radius_spin.setRange(0, 1200)
    dialog.nav_movement_precision_click_max_radius_spin.setSingleStep(10)

    dialog.nav_auto_click_cooldown_spin = QSpinBox()
    dialog.nav_auto_click_cooldown_spin.setRange(120, 2000)
    dialog.nav_auto_click_cooldown_spin.setSingleStep(20)

    dialog.nav_auto_min_target_delta_spin = QDoubleSpinBox()
    dialog.nav_auto_min_target_delta_spin.setRange(0.0, 100.0)
    dialog.nav_auto_min_target_delta_spin.setSingleStep(1.0)
    dialog.nav_auto_min_target_delta_spin.setDecimals(1)

    dialog.nav_bottom_click_guard_spin = QSpinBox()
    dialog.nav_bottom_click_guard_spin.setRange(0, 1200)
    dialog.nav_bottom_click_guard_spin.setSingleStep(20)

    dialog.nav_auto_click_radius_btn = QPushButton("自动估算点击半径")

    add_helpful_row(screen_layout, "角色屏幕坐标 (X/Y)", screen_center_layout, "校准后的游戏人物中心屏幕坐标；点击映射以这里为原点。")
    add_helpful_row(screen_layout, "运动映射比例", dialog.nav_movement_scale_factor_spin, "地图距离换算成屏幕点击距离的倍率；通常只做微调。")
    add_helpful_row(screen_layout, "真实可见范围(地图像素)", dialog.nav_game_view_map_size_spin, "橙色框大小，表示主画面真实可交互视野，不参与定位。")
    add_helpful_row(screen_layout, "最小点击半径(屏幕像素)", dialog.nav_movement_min_click_radius_spin, "点击点距离人物中心的下限，避免点得太近不移动。")
    add_helpful_row(screen_layout, "最大点击半径(屏幕像素)", dialog.nav_movement_max_click_radius_spin, "点击点距离人物中心的上限，避免点到 UI 或视野外。")
    add_helpful_row(screen_layout, "自动点击冷却(ms)", dialog.nav_auto_click_cooldown_spin, "自动导航两次移动点击之间的最小间隔。")
    add_helpful_row(screen_layout, "自动点击目标变化阈值", dialog.nav_auto_min_target_delta_spin, "普通路径中子目标变化小于该值时会抑制重复点击；锚点推进阶段会绕过这个抑制。")
    add_helpful_row(screen_layout, "底部禁点区域(px)", dialog.nav_bottom_click_guard_spin, "屏幕底部禁止点击高度，防止误点技能栏或 UI。")
    add_helpful_row(screen_layout, "近目标点击最大半径(屏幕像素)", dialog.nav_movement_precision_click_max_radius_spin, "靠近锚点/必经点/事件点时的精确点击上限；调小可减少冲过点后回头。")
    screen_layout.addRow(dialog.nav_auto_click_radius_btn)
    movement_layout.addWidget(screen_group)
    movement_layout.addStretch(1)


def build_path_section(dialog, path_layout) -> None:
    obstacle_group = QGroupBox("路径与障碍")
    obstacle_layout = QFormLayout(obstacle_group)

    dialog.nav_anchor_arrival_radius_spin = QSpinBox()
    dialog.nav_anchor_arrival_radius_spin.setRange(4, 200)
    dialog.nav_anchor_arrival_radius_spin.setSingleStep(2)

    dialog.nav_required_arrival_radius_spin = QSpinBox()
    dialog.nav_required_arrival_radius_spin.setRange(4, 240)
    dialog.nav_required_arrival_radius_spin.setSingleStep(2)

    dialog.nav_route_anchor_target_margin_spin = QDoubleSpinBox()
    dialog.nav_route_anchor_target_margin_spin.setRange(0.0, 300.0)
    dialog.nav_route_anchor_target_margin_spin.setSingleStep(2.0)
    dialog.nav_route_anchor_target_margin_spin.setDecimals(1)

    dialog.nav_exact_goal_click_enabled_chk = QCheckBox("启用近终点精确点击")

    dialog.nav_exact_goal_click_radius_spin = QSpinBox()
    dialog.nav_exact_goal_click_radius_spin.setRange(0, 300)
    dialog.nav_exact_goal_click_radius_spin.setSingleStep(5)

    dialog.nav_exact_goal_click_cooldown_spin = QSpinBox()
    dialog.nav_exact_goal_click_cooldown_spin.setRange(0, 3000)
    dialog.nav_exact_goal_click_cooldown_spin.setSingleStep(20)

    dialog.nav_exact_goal_recovery_suppress_spin = QSpinBox()
    dialog.nav_exact_goal_recovery_suppress_spin.setRange(0, 8000)
    dialog.nav_exact_goal_recovery_suppress_spin.setSingleStep(100)

    dialog.nav_movement_replan_throttle_spin = QSpinBox()
    dialog.nav_movement_replan_throttle_spin.setRange(0, 3000)
    dialog.nav_movement_replan_throttle_spin.setSingleStep(20)

    dialog.nav_fallback_replan_interval_spin = QSpinBox()
    dialog.nav_fallback_replan_interval_spin.setRange(0, 5000)
    dialog.nav_fallback_replan_interval_spin.setSingleStep(50)

    dialog.nav_movement_progress_timeout_spin = QSpinBox()
    dialog.nav_movement_progress_timeout_spin.setRange(200, 10000)
    dialog.nav_movement_progress_timeout_spin.setSingleStep(100)

    dialog.nav_movement_min_progress_delta_spin = QDoubleSpinBox()
    dialog.nav_movement_min_progress_delta_spin.setRange(0.0, 200.0)
    dialog.nav_movement_min_progress_delta_spin.setSingleStep(1.0)
    dialog.nav_movement_min_progress_delta_spin.setDecimals(1)

    dialog.nav_movement_max_recover_attempts_spin = QSpinBox()
    dialog.nav_movement_max_recover_attempts_spin.setRange(0, 10)
    dialog.nav_movement_max_recover_attempts_spin.setSingleStep(1)

    dialog.nav_movement_path_deviation_threshold_spin = QDoubleSpinBox()
    dialog.nav_movement_path_deviation_threshold_spin.setRange(8.0, 400.0)
    dialog.nav_movement_path_deviation_threshold_spin.setSingleStep(4.0)
    dialog.nav_movement_path_deviation_threshold_spin.setDecimals(1)

    dialog.nav_wall_erode_iterations_spin = QSpinBox()
    dialog.nav_wall_erode_iterations_spin.setRange(0, 5)
    dialog.nav_wall_erode_iterations_spin.setSingleStep(1)

    dialog.nav_path_start_clear_radius_spin = QSpinBox()
    dialog.nav_path_start_clear_radius_spin.setRange(0, 200)
    dialog.nav_path_start_clear_radius_spin.setSingleStep(5)

    dialog.nav_path_walkable_snap_radius_spin = QSpinBox()
    dialog.nav_path_walkable_snap_radius_spin.setRange(0, 200)
    dialog.nav_path_walkable_snap_radius_spin.setSingleStep(5)

    dialog.nav_local_probe_forward_spin = QDoubleSpinBox()
    dialog.nav_local_probe_forward_spin.setRange(0.0, 300.0)
    dialog.nav_local_probe_forward_spin.setSingleStep(2.0)
    dialog.nav_local_probe_forward_spin.setDecimals(1)

    dialog.nav_local_probe_lateral_spin = QDoubleSpinBox()
    dialog.nav_local_probe_lateral_spin.setRange(0.0, 300.0)
    dialog.nav_local_probe_lateral_spin.setSingleStep(2.0)
    dialog.nav_local_probe_lateral_spin.setDecimals(1)

    dialog.nav_recovery_probe_forward_min_spin = QDoubleSpinBox()
    dialog.nav_recovery_probe_forward_min_spin.setRange(0.0, 300.0)
    dialog.nav_recovery_probe_forward_min_spin.setSingleStep(2.0)
    dialog.nav_recovery_probe_forward_min_spin.setDecimals(1)

    dialog.nav_recovery_probe_forward_max_spin = QDoubleSpinBox()
    dialog.nav_recovery_probe_forward_max_spin.setRange(0.0, 500.0)
    dialog.nav_recovery_probe_forward_max_spin.setSingleStep(2.0)
    dialog.nav_recovery_probe_forward_max_spin.setDecimals(1)

    dialog.nav_recovery_probe_forward_multiplier_spin = QDoubleSpinBox()
    dialog.nav_recovery_probe_forward_multiplier_spin.setRange(0.0, 8.0)
    dialog.nav_recovery_probe_forward_multiplier_spin.setSingleStep(0.1)
    dialog.nav_recovery_probe_forward_multiplier_spin.setDecimals(2)

    dialog.nav_recovery_probe_lateral_spin = QDoubleSpinBox()
    dialog.nav_recovery_probe_lateral_spin.setRange(0.0, 300.0)
    dialog.nav_recovery_probe_lateral_spin.setSingleStep(2.0)
    dialog.nav_recovery_probe_lateral_spin.setDecimals(1)

    add_helpful_row(obstacle_layout, "A* 墙体侵蚀次数", dialog.nav_wall_erode_iterations_spin, "仅作用于导航障碍层，让视觉墙体变薄、窄通道更容易通过；不改变定位墙体。")
    add_helpful_row(obstacle_layout, "A* 起点清空半径(地图像素)", dialog.nav_path_start_clear_radius_spin, "寻路前清空人物附近障碍，避免定位点贴墙时起点被判进墙。")
    add_helpful_row(obstacle_layout, "A* 起终点吸附半径(地图像素)", dialog.nav_path_walkable_snap_radius_spin, "起点或目标落在障碍附近时，搜索半径内最近可走点。")
    add_helpful_row(obstacle_layout, "必经点完成半径(地图像素)", dialog.nav_required_arrival_radius_spin, "人物距离当前必经点小于该值时直接标记完成并切到下一个目标；调大更快跳点，调小更精确但更容易走走停停。")
    add_helpful_row(obstacle_layout, "锚点到达半径(地图像素)", dialog.nav_anchor_arrival_radius_spin, "距离当前辅助锚点小于该值时认为锚点已消费并切到下一个锚点。")
    add_helpful_row(obstacle_layout, "锚点走廊目标余量", dialog.nav_route_anchor_target_margin_spin, "A* 借助辅助锚点时，允许目标点后方多远范围内的锚点参与规划；越大越不容易漏锚点，越小越收敛。")
    add_helpful_row(obstacle_layout, "启用近终点精确点击", dialog.nav_exact_goal_click_enabled_chk, "接近当前路径终点/锚点时直接点击终点，减少绕点；如果必经点走走停停，可先关闭或缩小半径。")
    add_helpful_row(obstacle_layout, "近终点精确点击半径", dialog.nav_exact_goal_click_radius_spin, "人物距离路径终点小于该值，且大于当前目标停止半径时，进入精确点击终点逻辑；真实目标用必经点/事件半径，辅助锚点用锚点半径。")
    add_helpful_row(obstacle_layout, "近终点点击冷却(ms)", dialog.nav_exact_goal_click_cooldown_spin, "近终点精确点击阶段两次点击的最小间隔；用于调试靠近点位时是否过慢或过密。")
    add_helpful_row(obstacle_layout, "近终点恢复抑制(ms)", dialog.nav_exact_goal_recovery_suppress_spin, "进入精确终点点击后，短时间内不触发卡住恢复，避免刚靠近目标就左右探针。")
    add_helpful_row(obstacle_layout, "重规划节流(ms)", dialog.nav_movement_replan_throttle_spin, "同一目标连续重规划的最小间隔；过低会频繁规划，过高会让路径修正变慢。")
    add_helpful_row(obstacle_layout, "fallback 重规划间隔(ms)", dialog.nav_fallback_replan_interval_spin, "A* 失败进入局部探针 fallback 后，隔多久重新尝试 A*。")
    add_helpful_row(obstacle_layout, "卡住判定间隔(ms)", dialog.nav_movement_progress_timeout_spin, "在该时间内路径进度不足时触发恢复点击；调小会更快脱困。")
    add_helpful_row(obstacle_layout, "最小有效进度(地图像素)", dialog.nav_movement_min_progress_delta_spin, "卡住判定窗口内至少要前进的路径距离，低于该值认为没有明显移动。")
    add_helpful_row(obstacle_layout, "恢复尝试次数", dialog.nav_movement_max_recover_attempts_spin, "连续卡住时对当前锚点做侧向探测点击的次数，耗尽后强制重规划。")
    add_helpful_row(obstacle_layout, "路径偏离阈值(地图像素)", dialog.nav_movement_path_deviation_threshold_spin, "人物离当前规划路径过远时立即重规划。")
    add_helpful_row(obstacle_layout, "fallback 前进距离", dialog.nav_local_probe_forward_spin, "A* 完全失败时，沿目标方向临时点击的前进距离。")
    add_helpful_row(obstacle_layout, "fallback 侧向距离", dialog.nav_local_probe_lateral_spin, "A* 失败局部探针的左右偏移距离；用于绕开局部障碍。")
    add_helpful_row(obstacle_layout, "恢复探针前进最小值", dialog.nav_recovery_probe_forward_min_spin, "卡住恢复时前向探针距离下限。")
    add_helpful_row(obstacle_layout, "恢复探针前进最大值", dialog.nav_recovery_probe_forward_max_spin, "卡住恢复时前向探针距离上限。")
    add_helpful_row(obstacle_layout, "恢复探针锚点倍率", dialog.nav_recovery_probe_forward_multiplier_spin, "卡住恢复前进距离 = 锚点到达半径 × 该倍率，并受最小/最大值限制。")
    add_helpful_row(obstacle_layout, "恢复探针侧向距离", dialog.nav_recovery_probe_lateral_spin, "卡住恢复时左右探针偏移距离；调大更容易绕开障碍，但也更可能偏离路线。")
    path_layout.addWidget(obstacle_group)
    path_layout.addStretch(1)


def build_event_section(dialog, event_layout) -> None:
    event_group = QGroupBox("事件靠近/停稳")
    event_form_layout = QFormLayout(event_group)

    dialog.nav_event_approach_enabled_chk = QCheckBox("启用事件靠近停稳层")

    dialog.nav_event_visible_margin_spin = QSpinBox()
    dialog.nav_event_visible_margin_spin.setRange(0, 500)
    dialog.nav_event_visible_margin_spin.setSingleStep(5)

    dialog.nav_event_approach_lookahead_spin = QSpinBox()
    dialog.nav_event_approach_lookahead_spin.setRange(8, 240)
    dialog.nav_event_approach_lookahead_spin.setSingleStep(2)

    dialog.nav_event_approach_click_cooldown_spin = QSpinBox()
    dialog.nav_event_approach_click_cooldown_spin.setRange(120, 3000)
    dialog.nav_event_approach_click_cooldown_spin.setSingleStep(50)

    dialog.nav_event_stop_radius_spin = QSpinBox()
    dialog.nav_event_stop_radius_spin.setRange(4, 160)
    dialog.nav_event_stop_radius_spin.setSingleStep(2)

    dialog.nav_event_settle_ms_spin = QSpinBox()
    dialog.nav_event_settle_ms_spin.setRange(0, 5000)
    dialog.nav_event_settle_ms_spin.setSingleStep(100)

    dialog.nav_event_stable_frames_spin = QSpinBox()
    dialog.nav_event_stable_frames_spin.setRange(1, 20)
    dialog.nav_event_stable_frames_spin.setSingleStep(1)

    dialog.nav_event_max_motion_per_frame_spin = QDoubleSpinBox()
    dialog.nav_event_max_motion_per_frame_spin.setRange(0.0, 80.0)
    dialog.nav_event_max_motion_per_frame_spin.setSingleStep(1.0)
    dialog.nav_event_max_motion_per_frame_spin.setDecimals(1)

    dialog.nav_event_route_backtrack_margin_spin = QDoubleSpinBox()
    dialog.nav_event_route_backtrack_margin_spin.setRange(0.0, 300.0)
    dialog.nav_event_route_backtrack_margin_spin.setSingleStep(2.0)
    dialog.nav_event_route_backtrack_margin_spin.setDecimals(1)

    dialog.nav_event_required_forward_margin_spin = QDoubleSpinBox()
    dialog.nav_event_required_forward_margin_spin.setRange(0.0, 300.0)
    dialog.nav_event_required_forward_margin_spin.setSingleStep(2.0)
    dialog.nav_event_required_forward_margin_spin.setDecimals(1)

    dialog.nav_event_exit_forward_margin_spin = QDoubleSpinBox()
    dialog.nav_event_exit_forward_margin_spin.setRange(0.0, 500.0)
    dialog.nav_event_exit_forward_margin_spin.setSingleStep(2.0)
    dialog.nav_event_exit_forward_margin_spin.setDecimals(1)

    dialog.nav_event_fallback_player_radius_spin = QDoubleSpinBox()
    dialog.nav_event_fallback_player_radius_spin.setRange(0.0, 3000.0)
    dialog.nav_event_fallback_player_radius_spin.setSingleStep(20.0)
    dialog.nav_event_fallback_player_radius_spin.setDecimals(1)

    dialog.nav_event_fallback_static_margin_spin = QDoubleSpinBox()
    dialog.nav_event_fallback_static_margin_spin.setRange(0.0, 1000.0)
    dialog.nav_event_fallback_static_margin_spin.setSingleStep(10.0)
    dialog.nav_event_fallback_static_margin_spin.setDecimals(1)

    add_helpful_row(event_form_layout, "启用事件停稳层", dialog.nav_event_approach_enabled_chk, "启用后事件进入真实视野后先近距离收敛并停稳，再交给事件处理器触发。")
    add_helpful_row(event_form_layout, "真实视野边距(地图像素)", dialog.nav_event_visible_margin_spin, "事件点进入橙色真实视野框外加该边距后，切换到近距离靠近逻辑。")
    add_helpful_row(event_form_layout, "事件近距离 lookahead", dialog.nav_event_approach_lookahead_spin, "事件进入真实视野后的 A* 子目标前瞻距离；越小越收敛，越大越快但可能跑过。")
    add_helpful_row(event_form_layout, "事件点击冷却(ms)", dialog.nav_event_approach_click_cooldown_spin, "事件近距离靠近阶段两次移动点击的最小间隔，调大可减少绕点。")
    add_helpful_row(event_form_layout, "事件停靠半径(地图像素)", dialog.nav_event_stop_radius_spin, "人物距离事件前停靠点或事件中心小于该值时停止移动点击，开始等待停稳。")
    add_helpful_row(event_form_layout, "停稳等待(ms)", dialog.nav_event_settle_ms_spin, "到达事件附近后等待多久再允许事件处理器点击或按键。")
    add_helpful_row(event_form_layout, "停稳帧数", dialog.nav_event_stable_frames_spin, "连续多少帧位移足够小才认为角色已停稳。")
    add_helpful_row(event_form_layout, "停稳最大位移/帧", dialog.nav_event_max_motion_per_frame_spin, "停稳判断中每帧允许的最大地图位移，过小会等待更久。")
    add_helpful_row(event_form_layout, "事件路线回看余量", dialog.nav_event_route_backtrack_margin_spin, "有辅助锚点路线时，允许人物当前位置后方多远的事件仍参与调度，避免刚路过就丢事件。")
    add_helpful_row(event_form_layout, "必经点前事件余量", dialog.nav_event_required_forward_margin_spin, "当前目标是必经点时，允许必经点进度前方多远的事件插入；越大越容易提前处理事件。")
    add_helpful_row(event_form_layout, "出口前事件余量", dialog.nav_event_exit_forward_margin_spin, "当前目标是出口时，允许人物到出口范围外额外多远的事件插入。")
    add_helpful_row(event_form_layout, "无路线事件可见半径", dialog.nav_event_fallback_player_radius_spin, "没有辅助锚点路线/无法计算进度时，事件距离人物小于该值才允许参与调度。")
    add_helpful_row(event_form_layout, "无路线静态目标余量", dialog.nav_event_fallback_static_margin_spin, "没有路线进度时，事件距离必须不超过当前必经点/出口距离加该余量；防止远处事件抢掉近处必经点。")
    event_layout.addWidget(event_group)
    event_layout.addStretch(1)


def build_map_debug_section(dialog, map_layout) -> None:
    runtime_group = QGroupBox("地图与调试")
    runtime_layout = QFormLayout(runtime_group)

    dialog.nav_info_draw_scale = QLabel("N/A")

    dialog.nav_info_logical_center = QLineEdit("N/A")
    dialog.nav_info_logical_center.setReadOnly(True)

    dialog.nav_monitor_size_spin = QSpinBox()
    dialog.nav_monitor_size_spin.setRange(100, 2000)
    dialog.nav_monitor_size_spin.setSingleStep(10)
    dialog.nav_monitor_size_spin.setReadOnly(True)
    dialog.nav_monitor_size_spin.setButtonSymbols(QSpinBox.NoButtons)

    dialog.nav_fps_spin = QSpinBox()
    dialog.nav_fps_spin.setRange(1, 60)
    dialog.nav_fps_spin.setSingleStep(1)

    dialog.nav_visual_check_interval_spin = QSpinBox()
    dialog.nav_visual_check_interval_spin.setRange(0, 10000)
    dialog.nav_visual_check_interval_spin.setSingleStep(100)

    dialog.nav_visual_check_margin_spin = QSpinBox()
    dialog.nav_visual_check_margin_spin.setRange(40, 600)
    dialog.nav_visual_check_margin_spin.setSingleStep(10)

    dialog.nav_visual_match_min_conf_spin = QDoubleSpinBox()
    dialog.nav_visual_match_min_conf_spin.setRange(0.1, 0.99)
    dialog.nav_visual_match_min_conf_spin.setSingleStep(0.01)
    dialog.nav_visual_match_min_conf_spin.setDecimals(2)

    dialog.nav_visual_mismatch_threshold_spin = QDoubleSpinBox()
    dialog.nav_visual_mismatch_threshold_spin.setRange(4.0, 200.0)
    dialog.nav_visual_mismatch_threshold_spin.setSingleStep(2.0)
    dialog.nav_visual_mismatch_threshold_spin.setDecimals(1)

    dialog.nav_visual_mismatch_frames_spin = QSpinBox()
    dialog.nav_visual_mismatch_frames_spin.setRange(1, 10)
    dialog.nav_visual_mismatch_frames_spin.setSingleStep(1)

    dialog.nav_coord_raw_control_gap_spin = QDoubleSpinBox()
    dialog.nav_coord_raw_control_gap_spin.setRange(0.0, 300.0)
    dialog.nav_coord_raw_control_gap_spin.setSingleStep(2.0)
    dialog.nav_coord_raw_control_gap_spin.setDecimals(1)

    dialog.nav_coord_raw_jump_spin = QDoubleSpinBox()
    dialog.nav_coord_raw_jump_spin.setRange(0.0, 600.0)
    dialog.nav_coord_raw_jump_spin.setSingleStep(5.0)
    dialog.nav_coord_raw_jump_spin.setDecimals(1)

    dialog.nav_coord_route_deviation_spin = QDoubleSpinBox()
    dialog.nav_coord_route_deviation_spin.setRange(0.0, 600.0)
    dialog.nav_coord_route_deviation_spin.setSingleStep(5.0)
    dialog.nav_coord_route_deviation_spin.setDecimals(1)

    dialog.nav_coord_target_near_margin_spin = QDoubleSpinBox()
    dialog.nav_coord_target_near_margin_spin.setRange(0.0, 300.0)
    dialog.nav_coord_target_near_margin_spin.setSingleStep(2.0)
    dialog.nav_coord_target_near_margin_spin.setDecimals(1)

    dialog.nav_coord_target_stall_ms_spin = QSpinBox()
    dialog.nav_coord_target_stall_ms_spin.setRange(0, 10000)
    dialog.nav_coord_target_stall_ms_spin.setSingleStep(100)

    dialog.nav_coord_diagnostics_throttle_ms_spin = QSpinBox()
    dialog.nav_coord_diagnostics_throttle_ms_spin.setRange(0, 10000)
    dialog.nav_coord_diagnostics_throttle_ms_spin.setSingleStep(100)

    dialog.nav_coord_recovery_enabled_chk = QCheckBox("启用坐标异常重定位")

    dialog.nav_coord_recovery_score_spin = QSpinBox()
    dialog.nav_coord_recovery_score_spin.setRange(1, 20)
    dialog.nav_coord_recovery_score_spin.setSingleStep(1)

    dialog.nav_coord_recovery_window_ms_spin = QSpinBox()
    dialog.nav_coord_recovery_window_ms_spin.setRange(100, 20000)
    dialog.nav_coord_recovery_window_ms_spin.setSingleStep(100)

    dialog.nav_coord_recovery_cooldown_ms_spin = QSpinBox()
    dialog.nav_coord_recovery_cooldown_ms_spin.setRange(0, 30000)
    dialog.nav_coord_recovery_cooldown_ms_spin.setSingleStep(100)

    dialog.nav_coord_recovery_timeout_ms_spin = QSpinBox()
    dialog.nav_coord_recovery_timeout_ms_spin.setRange(100, 20000)
    dialog.nav_coord_recovery_timeout_ms_spin.setSingleStep(100)

    dialog.nav_coord_long_f2f_tracking_ms_spin = QSpinBox()
    dialog.nav_coord_long_f2f_tracking_ms_spin.setRange(0, 60000)
    dialog.nav_coord_long_f2f_tracking_ms_spin.setSingleStep(500)

    dialog.nav_coord_localization_sample_interval_ms_spin = QSpinBox()
    dialog.nav_coord_localization_sample_interval_ms_spin.setRange(0, 10000)
    dialog.nav_coord_localization_sample_interval_ms_spin.setSingleStep(100)

    dialog.nav_toggle_overlay_btn = QPushButton("切换调试幕布")
    dialog.nav_toggle_overlay_btn.setCheckable(True)

    add_helpful_row(runtime_layout, "地图精度 (Draw Scale)", dialog.nav_info_draw_scale, "当前地图绘制缩放，只读；必须与建图数据一致。")
    add_helpful_row(runtime_layout, "逻辑中心 (建图继承)", dialog.nav_info_logical_center, "小地图截图区域，只读；定位必须与建图环境一致。")
    add_helpful_row(runtime_layout, "截图大小 (建图继承)", dialog.nav_monitor_size_spin, "定位监视窗口大小，只读；来自建图配置。")
    add_helpful_row(runtime_layout, "导航刷新率 (FPS)", dialog.nav_fps_spin, "导航循环刷新率；过高会增加 CPU 和点击判断频率。")
    add_helpful_row(runtime_layout, "视觉校验间隔(ms)", dialog.nav_visual_check_interval_spin, "F2F 跟踪时隔多久用当前截图在大地图附近做一次模板校验；0 表示关闭自动视觉校验。")
    add_helpful_row(runtime_layout, "视觉校验搜索边距", dialog.nav_visual_check_margin_spin, "围绕当前人物位置的模板搜索边距，越大越能发现偏移但越耗 CPU。")
    add_helpful_row(runtime_layout, "视觉校验最低置信度", dialog.nav_visual_match_min_conf_spin, "截图贴回大地图的局部匹配分数低于该值时，不把偏移当作有效证据。")
    add_helpful_row(runtime_layout, "视觉偏移阈值(地图像素)", dialog.nav_visual_mismatch_threshold_spin, "截图最佳贴图位置与当前导航人物点的距离超过该值，才算一次视觉偏移。")
    add_helpful_row(runtime_layout, "视觉偏移连续帧数", dialog.nav_visual_mismatch_frames_spin, "连续多少次视觉校验都偏移，才触发一次强制重定位。")
    add_helpful_row(runtime_layout, "原始/控制坐标差阈值", dialog.nav_coord_raw_control_gap_spin, "原始定位点和控制平滑点差距超过该值时，记录坐标异常信号。")
    add_helpful_row(runtime_layout, "原始坐标跳变阈值", dialog.nav_coord_raw_jump_spin, "连续定位帧中原始坐标跳变超过该值时，记录 raw_jump 重定位信号。")
    add_helpful_row(runtime_layout, "路线偏离诊断阈值", dialog.nav_coord_route_deviation_spin, "人物控制点偏离辅助锚点路线超过该值时，记录路线偏离诊断。")
    add_helpful_row(runtime_layout, "近目标未完成余量", dialog.nav_coord_target_near_margin_spin, "人物已接近目标但还没进入完成半径时的诊断范围；用于发现绕点/半径过小。")
    add_helpful_row(runtime_layout, "近目标卡住时间(ms)", dialog.nav_coord_target_stall_ms_spin, "在近目标范围内停留超过该时间仍未完成，打印 near target not completed。")
    add_helpful_row(runtime_layout, "坐标诊断日志节流(ms)", dialog.nav_coord_diagnostics_throttle_ms_spin, "同类坐标诊断日志的最小打印间隔，避免日志刷屏。")
    add_helpful_row(runtime_layout, "启用异常重定位", dialog.nav_coord_recovery_enabled_chk, "关闭后只记录坐标诊断，不会因为异常信号主动触发全图重定位。")
    add_helpful_row(runtime_layout, "重定位触发分数", dialog.nav_coord_recovery_score_spin, "恢复窗口内异常信号累计分数达到该值后，请求一次强制重定位。")
    add_helpful_row(runtime_layout, "重定位信号窗口(ms)", dialog.nav_coord_recovery_window_ms_spin, "只统计该时间窗口内的异常信号；越大越容易累计触发。")
    add_helpful_row(runtime_layout, "重定位冷却(ms)", dialog.nav_coord_recovery_cooldown_ms_spin, "两次自动强制重定位之间的最小间隔，防止频繁全图匹配。")
    add_helpful_row(runtime_layout, "重定位等待超时(ms)", dialog.nav_coord_recovery_timeout_ms_spin, "发起强制重定位后，超过该时间还没有接受结果则判定本次重定位失败。")
    add_helpful_row(runtime_layout, "F2F 长跟踪阈值(ms)", dialog.nav_coord_long_f2f_tracking_ms_spin, "连续使用帧到帧跟踪超过该时间后，会更谨慎地观察是否需要全图校准。")
    add_helpful_row(runtime_layout, "定位样本日志间隔(ms)", dialog.nav_coord_localization_sample_interval_ms_spin, "坐标定位采样日志的最小间隔；调大可减少日志量。")
    runtime_layout.addRow(dialog.nav_toggle_overlay_btn)
    map_layout.addWidget(runtime_group)
    map_layout.addStretch(1)


def add_helpful_row(layout: QFormLayout, label: str, widget, help_text: str) -> None:
    label_widget = QLabel(f"{label}\n{help_text}")
    label_widget.setWordWrap(True)
    label_widget.setToolTip(help_text)
    label_widget.setStyleSheet("QLabel { color: #3f3f3f; }")
    if hasattr(widget, "setToolTip"):
        widget.setToolTip(help_text)
    layout.addRow(label_widget, widget)


def apply_parameter_help(dialog) -> None:
    help_map = {
        dialog.nav_wall_hsv_min_edit: "墙体颜色 HSV 下限，影响墙体识别。",
        dialog.nav_wall_hsv_max_edit: "墙体颜色 HSV 上限，影响墙体识别。",
        dialog.nav_fog_hsv_min_edit: "迷雾颜色 HSV 下限，影响未探索区域识别。",
        dialog.nav_fog_hsv_max_edit: "迷雾颜色 HSV 上限，影响未探索区域识别。",
        dialog.nav_player_hsv_min_edit: "玩家图标 HSV 下限，影响人物定位。",
        dialog.nav_player_hsv_max_edit: "玩家图标 HSV 上限，影响人物定位。",
        dialog.nav_chk_enable_wall: "启用后识别墙体并参与建图/导航障碍处理。",
        dialog.nav_chk_enable_fog: "启用后识别迷雾或未探索区域。",
        dialog.nav_chk_clahe_enabled: "增强小地图局部对比度，过高可能放大噪声。",
        dialog.nav_chk_deepen_enabled: "加深颜色差异，便于分离地图要素。",
        dialog.nav_chk_gamma_enabled: "调整亮度曲线，适合小地图偏暗或偏亮时使用。",
        dialog.nav_chk_tophat_enabled: "突出小地图细小高亮结构。",
        dialog.nav_chk_sat_filter_enabled: "按饱和度过滤噪声或 UI 干扰。",
        dialog.nav_chk_transparent_mode: "用于透明小地图或低对比度地图的特殊墙体判定。",
        dialog.nav_clahe_clip_spin: "CLAHE 对比度限制，越高增强越强。",
        dialog.nav_deepen_factor_spin: "颜色深化倍率，影响墙体和背景分离。",
        dialog.nav_gamma_value_spin: "Gamma 校正值，影响亮度曲线。",
        dialog.nav_tophat_strength_spin: "顶帽结果叠加强度，影响细节突出程度。",
        dialog.nav_tophat_kernel_size_spin: "顶帽形态学核大小，需为奇数更稳定。",
        dialog.nav_sat_filter_thresh_spin: "饱和度过滤阈值，低饱和区域会被压制。",
        dialog.nav_edge_low_spin: "Canny 边缘低阈值。",
        dialog.nav_edge_high_spin: "Canny 边缘高阈值。",
        dialog.nav_blue_boost_spin: "蓝色通道增强倍率。",
        dialog.nav_trans_sat_penalty_spin: "透明模式下低饱和区域惩罚强度。",
        dialog.nav_trans_wall_thresh_spin: "透明模式墙体判定阈值。",
        dialog.nav_sat_filter_radius_spin: "饱和度过滤的局部半径。",
        dialog.nav_wall_weight_spin: "墙体颜色结果权重。",
        dialog.nav_edge_weight_spin: "边缘检测结果权重。",
        dialog.nav_clahe_grid_spin: "CLAHE 分块网格大小。",
        dialog.nav_kernel_small_spin: "小形态学核大小，用于轻量开闭运算。",
        dialog.nav_kernel_medium_spin: "中形态学核大小，用于更强的连通/去噪。",
        dialog.nav_event_approach_enabled_chk: "事件近距离靠近和停稳门控的总开关。",
        dialog.nav_event_visible_margin_spin: "真实视野框额外边距，影响事件从远距离导航切入近距离收敛的时机。",
        dialog.nav_event_approach_lookahead_spin: "事件近距离阶段的路径前瞻距离。",
        dialog.nav_event_approach_click_cooldown_spin: "事件近距离阶段的点击节流。",
        dialog.nav_event_stop_radius_spin: "事件触发前停止移动点击的半径。",
        dialog.nav_event_settle_ms_spin: "事件触发前等待停稳的时间。",
        dialog.nav_event_stable_frames_spin: "事件触发前要求的连续稳定帧数。",
        dialog.nav_event_max_motion_per_frame_spin: "事件停稳判定允许的最大单帧位移。",
    }
    for widget, help_text in help_map.items():
        widget.setToolTip(help_text)
