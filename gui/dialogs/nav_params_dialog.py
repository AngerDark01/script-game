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
    QPushButton, QLabel, QSpinBox, QDoubleSpinBox, QCheckBox, QLineEdit, QWidget
)
from PySide6.QtCore import Qt, Signal

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

        dialog_layout.addWidget(adjustable_group)

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

        dialog_layout.addWidget(flags_group)

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

        dialog_layout.addWidget(numerical_group)

        # ==================== 只读信息区域 ====================
        # 创建地图与运动控制组，显示只读信息和运动控制参数
        info_group = QGroupBox("地图与运动控制")
        info_layout = QFormLayout(info_group)

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

        # 地图精度显示（只读）
        self.nav_info_draw_scale = QLabel("N/A")

        # 逻辑中心编辑框（可编辑）
        self.nav_info_logical_center = QLineEdit("N/A")

        # 截图大小调节
        self.nav_monitor_size_spin = QSpinBox()
        self.nav_monitor_size_spin.setRange(100, 2000)
        self.nav_monitor_size_spin.setSingleStep(10)

        # FPS 调节
        self.nav_fps_spin = QSpinBox()
        self.nav_fps_spin.setRange(1, 60)
        self.nav_fps_spin.setSingleStep(1)

        # 调试幕布切换按钮
        self.nav_toggle_overlay_btn = QPushButton("切换调试幕布")
        self.nav_toggle_overlay_btn.setCheckable(True)

        # 将控件添加到布局中
        info_layout.addRow("角色屏幕坐标 (X/Y):", screen_center_layout)
        info_layout.addRow("运动映射比例:", self.nav_movement_scale_factor_spin)
        info_layout.addRow("地图精度 (Draw Scale):", self.nav_info_draw_scale)
        info_layout.addRow("逻辑中心 (可编辑):", self.nav_info_logical_center)
        info_layout.addRow("截图大小 (Size):", self.nav_monitor_size_spin)
        info_layout.addRow("导航刷新率 (FPS):", self.nav_fps_spin)
        info_layout.addRow(self.nav_toggle_overlay_btn)

        dialog_layout.addWidget(info_group)

        # ==================== 动作和状态区域 ====================
        # 创建底部动作栏，包含保存按钮和状态标签
        action_layout = QHBoxLayout()
        self.nav_save_btn = QPushButton("保存当前导航参数")
        self.nav_status_label = QLabel("参数未加载")
        # 状态标签右对齐
        self.nav_status_label.setAlignment(Qt.AlignRight)

        action_layout.addWidget(self.nav_save_btn)
        # 状态标签使用拉伸因子占据剩余空间
        action_layout.addWidget(self.nav_status_label, 1)

        dialog_layout.addLayout(action_layout)

    def _connect_signals(self):
        """
        连接所有输入控件的信号到处理槽

        使用 `functools.partial` 为每个控件创建一个定制化的处理函数，
        该函数知道要更新配置对象中的哪个具体属性。
        这种方法避免了从 UI 完全重建配置的需要，确保了参数的精确更新。
        """
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
            self.nav_monitor_size_spin: (None, "monitor_size"),
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
            self.nav_info_logical_center: (None, "monitor_logical_center"),
        }
        for widget, (sub_config, attr) in text_widget_map.items():
            handler = functools.partial(self._update_config_text_value, sub_config, attr)
            widget.textChanged.connect(handler)

        # 连接保存按钮的点击信号
        self.nav_save_btn.clicked.connect(self.save_requested)

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

        # ==================== 断开信号连接 ====================
        # 防止在更新 UI 时触发 _on_ui_changed 方法
        for w in self.findChildren(QWidget):
            if hasattr(w, 'valueChanged'):
                try:
                    w.valueChanged.disconnect()
                except (TypeError, RuntimeError):
                    pass  # 没有连接的信号时忽略
            if hasattr(w, 'stateChanged'):
                try:
                    w.stateChanged.disconnect()
                except (TypeError, RuntimeError):
                    pass
            if hasattr(w, 'textChanged'):
                try:
                    w.textChanged.disconnect()
                except (TypeError, RuntimeError):
                    pass

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
        self.nav_info_logical_center.setText(str(config.monitor_logical_center))
        self.nav_monitor_size_spin.setValue(config.monitor_size)
        self.nav_movement_scale_factor_spin.setValue(config.movement_scale_factor)

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


