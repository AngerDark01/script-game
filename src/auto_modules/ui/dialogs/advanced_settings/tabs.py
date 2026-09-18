from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .presets import preset_names


def build_advanced_settings_ui(dialog) -> None:
    """Build advanced-settings tabs and footer controls on the dialog."""
    layout = QVBoxLayout(dialog)
    dialog.tab_widget = QTabWidget()
    dialog.tab_widget.addTab(create_preprocessing_tab(dialog), "图像预处理")
    dialog.tab_widget.addTab(create_feature_tab(dialog), "特征提取")
    dialog.tab_widget.addTab(create_param_management_tab(dialog), "参数管理")
    dialog.tab_widget.addTab(create_stitcher_tab(dialog), "拼接算法")
    layout.addWidget(dialog.tab_widget, 1)
    layout.addLayout(create_footer(dialog))


def create_info_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet(
        "color: #bdc3c7; font-size: 11px; font-style: italic; "
        "margin-bottom: 5px; background-color: #2c3e50; padding: 5px; border-radius: 3px;"
    )
    return label


def create_preprocessing_tab(dialog) -> QWidget:
    tab, layout = _scrollable_tab()

    blur_group = QGroupBox("高斯模糊")
    blur_layout = QVBoxLayout(blur_group)
    blur_layout.addWidget(create_info_label(
        "作用：去除图像噪点，平滑细节。\n"
        "调节：通常保持3。图像非常嘈杂时可调大。\n"
        "影响：过大会导致墙体模糊，丢失细节。"
    ))
    blur_controls = QHBoxLayout()
    blur_controls.addWidget(QLabel("模糊强度:"))
    dialog.blur_strength_spin = QSpinBox()
    dialog.blur_strength_spin.setRange(1, 15)
    dialog.blur_strength_spin.setSingleStep(2)
    dialog.blur_strength_spin.setValue(3)
    blur_controls.addWidget(dialog.blur_strength_spin)
    blur_layout.addLayout(blur_controls)
    layout.addWidget(blur_group)

    deepen_group = QGroupBox("颜色深化")
    deepen_layout = QVBoxLayout(deepen_group)
    deepen_layout.addWidget(create_info_label(
        "作用：增强特定颜色的墙体（如蓝色/红色），压暗背景。\n"
        "调节：蓝色地图建议开启并调高蓝色增强。\n"
        "影响：使特定颜色的墙体与背景对比更明显。"
    ))
    dialog.deepen_enabled_check = QCheckBox("启用颜色深化")
    deepen_layout.addWidget(dialog.deepen_enabled_check)
    contrast_layout = QHBoxLayout()
    contrast_layout.addWidget(QLabel("对比度增强系数:"))
    dialog.contrast_factor_spin = QDoubleSpinBox()
    dialog.contrast_factor_spin.setRange(0.5, 3.0)
    dialog.contrast_factor_spin.setSingleStep(0.1)
    dialog.contrast_factor_spin.setValue(1.2)
    contrast_layout.addWidget(dialog.contrast_factor_spin)
    contrast_layout.addWidget(QLabel("(α值，值越大对比度越高)"))
    deepen_layout.addLayout(contrast_layout)
    blue_layout = QHBoxLayout()
    blue_layout.addWidget(QLabel("蓝色通道增强:"))
    dialog.blue_boost_spin = QDoubleSpinBox()
    dialog.blue_boost_spin.setRange(0.5, 3.0)
    dialog.blue_boost_spin.setSingleStep(0.1)
    dialog.blue_boost_spin.setValue(1.1)
    blue_layout.addWidget(dialog.blue_boost_spin)
    blue_layout.addWidget(QLabel("(蓝色通道乘数)"))
    deepen_layout.addLayout(blue_layout)
    layout.addWidget(deepen_group)

    gamma_group = QGroupBox("Gamma校正 (中间调压暗)")
    gamma_layout = QVBoxLayout(gamma_group)
    gamma_layout.addWidget(create_info_label(
        "作用：压暗中间调（灰色背景），保留高光（墙体）。\n"
        "调节：背景噪点多、像雪花一样时，调大Gamma值。\n"
        "影响：值越大背景越黑，越干净，但可能丢失暗淡的墙体。"
    ))
    gamma_controls = QHBoxLayout()
    dialog.gamma_enabled_check = QCheckBox("启用Gamma校正")
    gamma_controls.addWidget(dialog.gamma_enabled_check)
    gamma_controls.addWidget(QLabel("Gamma值:"))
    dialog.gamma_value_spin = QDoubleSpinBox()
    dialog.gamma_value_spin.setRange(0.1, 5.0)
    dialog.gamma_value_spin.setSingleStep(0.1)
    dialog.gamma_value_spin.setValue(2.0)
    dialog.gamma_value_spin.setToolTip("值越大，中间调越暗。用于压暗背景噪音，突出高亮墙体。")
    gamma_controls.addWidget(dialog.gamma_value_spin)
    gamma_layout.addLayout(gamma_controls)
    layout.addWidget(gamma_group)

    tophat_group = QGroupBox("TopHat结构提取 (增强细微线条)")
    tophat_layout = QVBoxLayout(tophat_group)
    tophat_layout.addWidget(create_info_label(
        "作用：提取比背景亮的小尺寸结构（如细墙体），无视背景亮度变化。\n"
        "调节：核大小应略大于墙体宽度。增强强度控制提取出来的亮度。\n"
        "影响：能有效连接断裂的墙体，解决光照不均匀问题。"
    ))
    dialog.tophat_enabled_check = QCheckBox("启用TopHat")
    tophat_layout.addWidget(dialog.tophat_enabled_check)
    tophat_params = QHBoxLayout()
    tophat_params.addWidget(QLabel("核大小:"))
    dialog.tophat_kernel_spin = QSpinBox()
    dialog.tophat_kernel_spin.setRange(3, 31)
    dialog.tophat_kernel_spin.setSingleStep(2)
    dialog.tophat_kernel_spin.setValue(15)
    dialog.tophat_kernel_spin.setToolTip("结构元素的尺寸。应略大于墙体宽度。")
    tophat_params.addWidget(dialog.tophat_kernel_spin)
    tophat_params.addWidget(QLabel("增强强度:"))
    dialog.tophat_strength_spin = QSpinBox()
    dialog.tophat_strength_spin.setRange(1, 10)
    dialog.tophat_strength_spin.setValue(4)
    dialog.tophat_strength_spin.setToolTip("提取出的结构增强倍数。")
    tophat_params.addWidget(dialog.tophat_strength_spin)
    tophat_layout.addLayout(tophat_params)
    layout.addWidget(tophat_group)

    clahe_group = QGroupBox("CLAHE增强")
    clahe_layout = QVBoxLayout(clahe_group)
    clahe_layout.addWidget(create_info_label(
        "作用：自适应直方图均衡，增强局部对比度。\n"
        "调节：裁剪限制越小，对比度增强越温和；网格越大，处理越粗糙。\n"
        "影响：让暗处的墙体也能被识别出来，但也会放大噪点。"
    ))
    dialog.clahe_enabled_check = QCheckBox("启用CLAHE增强")
    clahe_layout.addWidget(dialog.clahe_enabled_check)
    clahe_params_layout = QHBoxLayout()
    clip_layout = QVBoxLayout()
    clip_layout.addWidget(QLabel("CLAHE裁剪限制:"))
    dialog.clahe_clip_spin = QDoubleSpinBox()
    dialog.clahe_clip_spin.setRange(0.1, 10.0)
    dialog.clahe_clip_spin.setSingleStep(0.1)
    dialog.clahe_clip_spin.setValue(2.0)
    clip_layout.addWidget(dialog.clahe_clip_spin)
    clahe_params_layout.addLayout(clip_layout)
    grid_layout = QVBoxLayout()
    grid_layout.addWidget(QLabel("CLAHE网格大小:"))
    dialog.clahe_grid_spin = QSpinBox()
    dialog.clahe_grid_spin.setRange(2, 32)
    dialog.clahe_grid_spin.setSingleStep(1)
    dialog.clahe_grid_spin.setValue(8)
    grid_layout.addWidget(dialog.clahe_grid_spin)
    clahe_params_layout.addLayout(grid_layout)
    clahe_layout.addLayout(clahe_params_layout)
    layout.addWidget(clahe_group)

    layout.addStretch(1)
    return tab


def create_feature_tab(dialog) -> QWidget:
    tab, layout = _scrollable_tab()

    trans_group = QGroupBox("半透明地图模式 (针对灰色线条地图)")
    trans_layout = QVBoxLayout(trans_group)
    trans_layout.addWidget(create_info_label(
        "作用：专为半透明/灰白地图设计的特殊提取算法。\n"
        "原理：基于亮度(V)与饱和度(S)的差值来提取墙体 (墙体通常亮且白)。\n"
        "影响：开启后将忽略HSV颜色范围，使用专用算法。"
    ))
    dialog.transparent_mode_check = QCheckBox("启用透明地图模式")
    trans_layout.addWidget(dialog.transparent_mode_check)
    thresh_layout = QHBoxLayout()
    thresh_layout.addWidget(QLabel("灰白提取阈值 (V-S):"))
    dialog.trans_wall_thresh_spin = QSpinBox()
    dialog.trans_wall_thresh_spin.setRange(0, 255)
    dialog.trans_wall_thresh_spin.setValue(60)
    thresh_layout.addWidget(dialog.trans_wall_thresh_spin)
    thresh_layout.addWidget(QLabel("(值越大只保留越白的部分)"))
    trans_layout.addLayout(thresh_layout)
    penalty_layout = QHBoxLayout()
    penalty_layout.addWidget(QLabel("饱和度惩罚系数:"))
    dialog.trans_sat_penalty_spin = QDoubleSpinBox()
    dialog.trans_sat_penalty_spin.setRange(0.0, 5.0)
    dialog.trans_sat_penalty_spin.setSingleStep(0.1)
    dialog.trans_sat_penalty_spin.setValue(1.5)
    dialog.trans_sat_penalty_spin.setToolTip("用于抑制彩色区域。分数 = V - S * 系数。系数越大，彩色区域得分越低。")
    penalty_layout.addWidget(dialog.trans_sat_penalty_spin)
    trans_layout.addLayout(penalty_layout)
    layout.addWidget(trans_group)

    sat_group = QGroupBox("饱和度过滤 (解决彩色地图问题)")
    sat_layout = QVBoxLayout(sat_group)
    sat_layout.addWidget(create_info_label(
        "作用：强制去除高饱和度的彩色区域（如玩家箭头、技能特效）。\n"
        "调节：蓝色/彩色地图请【关闭】或【设置过滤半径】（只过滤玩家周围）。\n"
        "影响：在白色地图中能完美去除箭头；但在彩色地图中会误删墙体。"
    ))
    dialog.sat_filter_check = QCheckBox("启用饱和度过滤 (去除彩色杂点)")
    sat_layout.addWidget(dialog.sat_filter_check)
    sat_thresh_layout = QHBoxLayout()
    sat_thresh_layout.addWidget(QLabel("过滤阈值:"))
    dialog.sat_thresh_spin = QSpinBox()
    dialog.sat_thresh_spin.setRange(0, 255)
    dialog.sat_thresh_spin.setValue(40)
    sat_thresh_layout.addWidget(dialog.sat_thresh_spin)
    sat_thresh_layout.addWidget(QLabel("(S通道，>此值被视为杂点)"))
    sat_layout.addLayout(sat_thresh_layout)
    radius_layout = QHBoxLayout()
    radius_layout.addWidget(QLabel("过滤半径:"))
    dialog.sat_radius_spin = QSpinBox()
    dialog.sat_radius_spin.setRange(0, 500)
    dialog.sat_radius_spin.setValue(0)
    radius_layout.addWidget(dialog.sat_radius_spin)
    radius_layout.addWidget(QLabel("(0=全局过滤, >0=仅过滤玩家周围)"))
    sat_layout.addLayout(radius_layout)
    layout.addWidget(sat_group)

    edge_group = QGroupBox("Canny边缘检测")
    edge_layout = QVBoxLayout(edge_group)
    edge_layout.addWidget(create_info_label(
        "作用：检测图像中的边缘线条（用于辅助配准）。\n"
        "调节：低阈值越小，细节越多（但也越噪）；高阈值越大，边缘要求越严格。\n"
        "影响：提供额外的几何特征，帮助在纯色墙体上进行配准。"
    ))
    low_layout = QHBoxLayout()
    low_layout.addWidget(QLabel("低阈值:"))
    dialog.edge_low_spin = QSpinBox()
    dialog.edge_low_spin.setRange(0, 255)
    dialog.edge_low_spin.setValue(50)
    low_layout.addWidget(dialog.edge_low_spin)
    edge_layout.addLayout(low_layout)
    high_layout = QHBoxLayout()
    high_layout.addWidget(QLabel("高阈值:"))
    dialog.edge_high_spin = QSpinBox()
    dialog.edge_high_spin.setRange(0, 255)
    dialog.edge_high_spin.setValue(150)
    high_layout.addWidget(dialog.edge_high_spin)
    edge_layout.addLayout(high_layout)
    layout.addWidget(edge_group)

    weight_group = QGroupBox("特征融合权重")
    weight_layout = QVBoxLayout(weight_group)
    weight_layout.addWidget(create_info_label(
        "作用：决定最终用于配准的图像中，各部分特征的占比。\n"
        "调节：墙体权重通常最高；边缘权重次之；灰度权重用于补充纹理。\n"
        "影响：权重分配不当可能导致配准偏向于噪点而非真实墙体。"
    ))
    wall_w_layout = QHBoxLayout()
    wall_w_layout.addWidget(QLabel("墙壁层权重:"))
    dialog.wall_weight_spin = QSpinBox()
    dialog.wall_weight_spin.setRange(0, 100)
    dialog.wall_weight_spin.setValue(50)
    wall_w_layout.addWidget(dialog.wall_weight_spin)
    weight_layout.addLayout(wall_w_layout)
    edge_w_layout = QHBoxLayout()
    edge_w_layout.addWidget(QLabel("边缘层权重:"))
    dialog.edge_weight_spin = QSpinBox()
    dialog.edge_weight_spin.setRange(0, 100)
    dialog.edge_weight_spin.setValue(30)
    edge_w_layout.addWidget(dialog.edge_weight_spin)
    weight_layout.addLayout(edge_w_layout)
    gray_w_layout = QHBoxLayout()
    gray_w_layout.addWidget(QLabel("灰度层权重:"))
    dialog.gray_weight_spin = QSpinBox()
    dialog.gray_weight_spin.setRange(0, 100)
    dialog.gray_weight_spin.setValue(20)
    gray_w_layout.addWidget(dialog.gray_weight_spin)
    weight_layout.addLayout(gray_w_layout)
    layout.addWidget(weight_group)

    layout.addStretch(1)
    return tab


def create_param_management_tab(dialog) -> QWidget:
    tab, layout = _scrollable_tab()

    save_group = QGroupBox("保存参数")
    save_layout = QVBoxLayout(save_group)
    save_btn_layout = QHBoxLayout()
    dialog.save_current_btn = QPushButton("保存当前参数")
    dialog.save_current_btn.clicked.connect(dialog.save_current_params)
    save_btn_layout.addWidget(dialog.save_current_btn)
    dialog.param_name_edit = QLineEdit()
    dialog.param_name_edit.setPlaceholderText("输入参数配置名称")
    save_btn_layout.addWidget(dialog.param_name_edit)
    save_layout.addLayout(save_btn_layout)
    dialog.save_status_label = QLabel("")
    save_layout.addWidget(dialog.save_status_label)
    layout.addWidget(save_group)

    load_group = QGroupBox("加载参数")
    load_layout = QVBoxLayout(load_group)
    load_btn_layout = QHBoxLayout()
    dialog.load_params_btn = QPushButton("浏览并加载参数")
    dialog.load_params_btn.clicked.connect(dialog.load_params_from_file)
    load_btn_layout.addWidget(dialog.load_params_btn)
    dialog.apply_loaded_btn = QPushButton("应用加载的参数")
    dialog.apply_loaded_btn.clicked.connect(dialog.apply_loaded_params)
    load_btn_layout.addWidget(dialog.apply_loaded_btn)
    load_layout.addLayout(load_btn_layout)
    dialog.loaded_params_text = QTextEdit()
    dialog.loaded_params_text.setMaximumHeight(150)
    dialog.loaded_params_text.setReadOnly(True)
    load_layout.addWidget(dialog.loaded_params_text)
    layout.addWidget(load_group)

    preset_group = QGroupBox("预设参数")
    preset_layout = QHBoxLayout(preset_group)
    dialog.preset_combo = QComboBox()
    dialog.preset_combo.addItems(preset_names())
    preset_layout.addWidget(dialog.preset_combo)
    dialog.apply_preset_btn = QPushButton("应用预设")
    dialog.apply_preset_btn.clicked.connect(dialog.apply_preset)
    preset_layout.addWidget(dialog.apply_preset_btn)
    layout.addWidget(preset_group)

    layout.addStretch(1)
    return tab


def create_stitcher_tab(dialog) -> QWidget:
    tab, layout = _scrollable_tab()

    match_group = QGroupBox("配准参数 (Frame-to-Frame)")
    match_layout = QVBoxLayout(match_group)
    match_layout.addWidget(create_info_label(
        "作用：控制帧与帧之间（F2F）的匹配严格程度。\n"
        "调节：如果经常出现红色❌（配准失败），请调低阈值。\n"
        "影响：阈值过低可能导致误匹配（地图乱飞）；阈值过高会导致断连。"
    ))
    conf_layout = QHBoxLayout()
    conf_layout.addWidget(QLabel("F2F匹配阈值:"))
    dialog.conf_thresh_spin = QDoubleSpinBox()
    dialog.conf_thresh_spin.setRange(0.1, 0.9)
    dialog.conf_thresh_spin.setSingleStep(0.05)
    dialog.conf_thresh_spin.setValue(0.30)
    dialog.conf_thresh_spin.setToolTip("Frame-to-Frame匹配的最低置信度。低于此值视为匹配失败。")
    conf_layout.addWidget(dialog.conf_thresh_spin)
    match_layout.addLayout(conf_layout)
    layout.addWidget(match_group)

    anchor_group = QGroupBox("锚点参数 (Keyframe Anchor)")
    anchor_layout = QVBoxLayout(anchor_group)
    anchor_layout.addWidget(create_info_label(
        "作用：控制关键帧（Anchor）的切换频率。\n"
        "调节：调高=频繁切换（精度高但累积误差大）；调低=很少切换（稳但可能跟丢）。\n"
        "影响：这是防止地图“漂移”和“双眼皮”的核心机制。"
    ))
    key_layout = QHBoxLayout()
    key_layout.addWidget(QLabel("关键帧维持阈值:"))
    dialog.keyframe_thresh_spin = QDoubleSpinBox()
    dialog.keyframe_thresh_spin.setRange(0.1, 0.9)
    dialog.keyframe_thresh_spin.setSingleStep(0.05)
    dialog.keyframe_thresh_spin.setValue(0.25)
    dialog.keyframe_thresh_spin.setToolTip("只要与关键帧的匹配度高于此值，就不切换关键帧。用于减少累积误差。")
    key_layout.addWidget(dialog.keyframe_thresh_spin)
    anchor_layout.addLayout(key_layout)
    layout.addWidget(anchor_group)

    merge_group = QGroupBox("融合参数 (Weighted Merge)")
    merge_layout = QVBoxLayout(merge_group)
    merge_layout.addWidget(create_info_label(
        "作用：控制地图的更新速度和抗噪能力。\n"
        "调节：增量越小，墙体变实越慢，但抗噪越好；最大权重控制墙体'厚度'上限。\n"
        "影响：防止单帧的错误识别污染整个地图。"
    ))
    add_layout = QHBoxLayout()
    add_layout.addWidget(QLabel("单帧权重增量:"))
    dialog.weight_add_spin = QDoubleSpinBox()
    dialog.weight_add_spin.setRange(0.05, 1.0)
    dialog.weight_add_spin.setSingleStep(0.05)
    dialog.weight_add_spin.setValue(0.3)
    dialog.weight_add_spin.setToolTip("每帧匹配成功后，墙体权重的增加值。值越小越抗噪，但更新越慢。")
    add_layout.addWidget(dialog.weight_add_spin)
    merge_layout.addLayout(add_layout)
    cap_layout = QHBoxLayout()
    cap_layout.addWidget(QLabel("最大权重限制:"))
    dialog.weight_cap_spin = QDoubleSpinBox()
    dialog.weight_cap_spin.setRange(1.0, 20.0)
    dialog.weight_cap_spin.setSingleStep(0.5)
    dialog.weight_cap_spin.setValue(5.0)
    dialog.weight_cap_spin.setToolTip("权重的上限值。防止权重无限累积。")
    cap_layout.addWidget(dialog.weight_cap_spin)
    merge_layout.addLayout(cap_layout)
    layout.addWidget(merge_group)

    layout.addStretch(1)
    return tab


def create_footer(dialog) -> QHBoxLayout:
    button_layout = QHBoxLayout()
    dialog.apply_btn = QPushButton("应用参数")
    dialog.apply_btn.clicked.connect(dialog.apply_params)
    button_layout.addWidget(dialog.apply_btn)
    dialog.reset_btn = QPushButton("重置为默认")
    dialog.reset_btn.clicked.connect(dialog.reset_to_default)
    button_layout.addWidget(dialog.reset_btn)
    dialog.ok_btn = QPushButton("确定")
    dialog.ok_btn.clicked.connect(dialog.accept)
    button_layout.addWidget(dialog.ok_btn)
    dialog.cancel_btn = QPushButton("取消")
    dialog.cancel_btn.clicked.connect(dialog.reject)
    button_layout.addWidget(dialog.cancel_btn)
    return button_layout


def _scrollable_tab() -> tuple[QWidget, QVBoxLayout]:
    tab = QWidget()
    outer_layout = QVBoxLayout(tab)
    outer_layout.setContentsMargins(0, 0, 0, 0)
    scroll_area = QScrollArea()
    scroll_area.setWidgetResizable(True)
    scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    content = QWidget()
    layout = QVBoxLayout(content)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(8)
    scroll_area.setWidget(content)
    outer_layout.addWidget(scroll_area)
    return tab, layout
