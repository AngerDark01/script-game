from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ....widgets.collapsible_group import CollapsibleMapGroup


def build_mapping_ui(owner) -> None:
    """Build the mapping page layout and write expected widgets back to owner."""
    layout = QHBoxLayout(owner)
    control_panel = create_mapping_control_panel(owner)
    layout.addWidget(control_panel, 1)
    display_panel = create_mapping_display_panel(owner)
    layout.addWidget(display_panel, 3)


def create_mapping_control_panel(owner) -> QWidget:
    scroll_area = QScrollArea()
    scroll_area.setWidgetResizable(True)
    scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    scroll_area.setWidget(create_mapping_control_content(owner))
    owner.control_scroll_area = scroll_area
    return scroll_area


def create_mapping_control_content(owner) -> QWidget:
    panel = QWidget()
    layout = QVBoxLayout(panel)

    region_group = QGroupBox("1. 监控区域")
    region_layout = QVBoxLayout()
    owner.select_region_btn = QPushButton("🖱️ 画框选择区域")
    owner.select_region_btn.clicked.connect(owner.select_region)
    region_layout.addWidget(owner.select_region_btn)
    owner.select_center_btn = QPushButton("🎯 选择人物中心点")
    owner.select_center_btn.clicked.connect(owner.select_center_point)
    region_layout.addWidget(owner.select_center_btn)
    owner.size_label = QLabel("截图大小:")
    region_layout.addWidget(owner.size_label)
    owner.size_spin = QSpinBox()
    owner.size_spin.setRange(100, 1000)
    owner.size_spin.setValue(320)
    owner.size_spin.valueChanged.connect(owner.update_capture_size)
    region_layout.addWidget(owner.size_spin)
    owner.color_picker_btn = QPushButton("🎨 选择颜色")
    owner.color_picker_btn.clicked.connect(owner.open_color_picker)
    owner.color_picker_btn.setEnabled(False)
    region_layout.addWidget(owner.color_picker_btn)
    owner.region_label = QLabel("未选择区域")
    owner.region_label.setWordWrap(True)
    region_layout.addWidget(owner.region_label)
    region_group.setLayout(region_layout)
    layout.addWidget(region_group)

    monitor_group = QGroupBox("2. 监控控制")
    monitor_layout = QVBoxLayout()
    fps_layout = QHBoxLayout()
    fps_layout.addWidget(QLabel("帧率(FPS):"))
    owner.fps_spin = QSpinBox()
    owner.fps_spin.setRange(1, 60)
    owner.fps_spin.setValue(10)
    fps_layout.addWidget(owner.fps_spin)
    monitor_layout.addLayout(fps_layout)
    owner.start_btn = QPushButton("▶️ 开始监控")
    owner.start_btn.clicked.connect(owner.toggle_monitoring)
    owner.start_btn.setEnabled(False)
    monitor_layout.addWidget(owner.start_btn)
    owner.reset_btn = QPushButton("🔄 重置地图")
    owner.reset_btn.clicked.connect(owner.reset_map)
    monitor_layout.addWidget(owner.reset_btn)
    owner.save_btn = QPushButton("💾 保存地图")
    owner.save_btn.clicked.connect(owner.save_map)
    monitor_layout.addWidget(owner.save_btn)

    owner.topmost_check = QCheckBox("置顶显示")
    owner.topmost_check.setChecked(True)
    owner.topmost_check.stateChanged.connect(owner.update_topmost)
    monitor_layout.addWidget(owner.topmost_check)

    monitor_group.setLayout(monitor_layout)
    layout.addWidget(monitor_group)

    geometry_group = QGroupBox("3. 高清绘图参数 (新地图生效)")
    geometry_layout = QVBoxLayout()

    owner.draw_scale_spin = QDoubleSpinBox()
    owner.draw_scale_spin.setRange(1.0, 4.0)
    owner.draw_scale_spin.setSingleStep(0.5)
    owner.draw_scale_spin.setDecimals(1)
    owner.draw_scale_spin.setValue(float(owner.app_context.stitcher.draw_scale))
    owner.draw_scale_spin.valueChanged.connect(owner.update_geometry_params)
    geometry_layout.addWidget(QLabel("绘图倍率 Draw Scale"))
    geometry_layout.addWidget(owner.draw_scale_spin)

    owner.canvas_size_spin = QSpinBox()
    owner.canvas_size_spin.setRange(3000, 12000)
    owner.canvas_size_spin.setSingleStep(500)
    owner.canvas_size_spin.setValue(int(owner.app_context.stitcher.canvas_size))
    owner.canvas_size_spin.valueChanged.connect(owner.update_geometry_params)
    geometry_layout.addWidget(QLabel("画布大小 Canvas Size"))
    geometry_layout.addWidget(owner.canvas_size_spin)

    owner.player_clear_radius_spin = QSpinBox()
    owner.player_clear_radius_spin.setRange(0, 120)
    owner.player_clear_radius_spin.setSingleStep(2)
    owner.player_clear_radius_spin.setValue(int(getattr(owner.app_context.recognizer, "player_clear_radius", 22)))
    owner.player_clear_radius_spin.valueChanged.connect(owner.update_geometry_params)
    geometry_layout.addWidget(QLabel("人物动态擦除半径(小地图像素)"))
    geometry_layout.addWidget(owner.player_clear_radius_spin)

    owner.wall_close_kernel_spin = QSpinBox()
    owner.wall_close_kernel_spin.setRange(1, 15)
    owner.wall_close_kernel_spin.setSingleStep(2)
    owner.wall_close_kernel_spin.setValue(int(getattr(owner.app_context.stitcher, "wall_close_kernel_size", 3)))
    owner.wall_close_kernel_spin.valueChanged.connect(owner.update_geometry_params)
    geometry_layout.addWidget(QLabel("墙体闭运算核(奇数)"))
    geometry_layout.addWidget(owner.wall_close_kernel_spin)

    geometry_hint = QLabel("draw_scale/canvas_size 只在重置地图后生效；推荐 3.0 + 7500。")
    geometry_hint.setWordWrap(True)
    geometry_layout.addWidget(geometry_hint)

    geometry_group.setLayout(geometry_layout)
    layout.addWidget(geometry_group)

    merge_group = QGroupBox("3. 融合参数 (Weighted Merge)")
    merge_layout = QVBoxLayout()
    info_label = QLabel("当前采用高精度加权融合模式。\n该模式通过累积多帧置信度来消除噪音。")
    info_label.setWordWrap(True)
    merge_layout.addWidget(info_label)
    owner.weight_label = QLabel("单帧置信度增量 (0.1-1.0):")
    merge_layout.addWidget(owner.weight_label)
    owner.weight_spin = QDoubleSpinBox()
    owner.weight_spin.setRange(0.05, 1.0)
    owner.weight_spin.setSingleStep(0.05)
    owner.weight_spin.setValue(0.3)
    owner.weight_spin.valueChanged.connect(owner.update_merge_params)
    merge_layout.addWidget(owner.weight_spin)
    merge_group.setLayout(merge_layout)
    layout.addWidget(merge_group)

    hsv_group = QGroupBox("4. HSV参数")
    hsv_layout = QVBoxLayout()
    owner.wall_check = QCheckBox("墙壁识别")
    owner.wall_check.setChecked(True)
    owner.wall_check.stateChanged.connect(owner.update_hsv_params)
    hsv_layout.addWidget(owner.wall_check)
    owner.fog_check = QCheckBox("迷雾识别")
    owner.fog_check.setChecked(True)
    owner.fog_check.stateChanged.connect(owner.update_hsv_params)
    hsv_layout.addWidget(owner.fog_check)
    hsv_group.setLayout(hsv_layout)
    layout.addWidget(hsv_group)

    feature_group = QGroupBox("5. 特征参数")
    feature_layout = QVBoxLayout()

    owner.clahe_check = QCheckBox("启用CLAHE增强")
    owner.clahe_check.setChecked(True)
    owner.clahe_check.stateChanged.connect(owner.update_feature_params)
    feature_layout.addWidget(owner.clahe_check)

    owner.deepen_check = QCheckBox("启用颜色深化(蓝)")
    owner.deepen_check.setChecked(True)
    owner.deepen_check.stateChanged.connect(owner.update_feature_params)
    feature_layout.addWidget(owner.deepen_check)

    owner.wall_weight_spin = QSpinBox()
    owner.wall_weight_spin.setRange(0, 100)
    owner.wall_weight_spin.setValue(50)
    owner.wall_weight_spin.valueChanged.connect(owner.update_feature_params)
    feature_layout.addWidget(QLabel("墙壁权重"))
    feature_layout.addWidget(owner.wall_weight_spin)

    owner.edge_weight_spin = QSpinBox()
    owner.edge_weight_spin.setRange(0, 100)
    owner.edge_weight_spin.setValue(30)
    owner.edge_weight_spin.valueChanged.connect(owner.update_feature_params)
    feature_layout.addWidget(QLabel("边缘权重"))
    feature_layout.addWidget(owner.edge_weight_spin)

    owner.gray_weight_spin = QSpinBox()
    owner.gray_weight_spin.setRange(0, 100)
    owner.gray_weight_spin.setValue(20)
    owner.gray_weight_spin.valueChanged.connect(owner.update_feature_params)
    feature_layout.addWidget(QLabel("灰度权重"))
    feature_layout.addWidget(owner.gray_weight_spin)

    owner.canny_low_spin = QSpinBox()
    owner.canny_low_spin.setRange(0, 255)
    owner.canny_low_spin.setValue(50)
    owner.canny_low_spin.valueChanged.connect(owner.update_feature_params)
    feature_layout.addWidget(QLabel("Canny低阈值"))
    feature_layout.addWidget(owner.canny_low_spin)

    owner.canny_high_spin = QSpinBox()
    owner.canny_high_spin.setRange(0, 255)
    owner.canny_high_spin.setValue(150)
    owner.canny_high_spin.valueChanged.connect(owner.update_feature_params)
    feature_layout.addWidget(QLabel("Canny高阈值"))
    feature_layout.addWidget(owner.canny_high_spin)

    owner.advanced_settings_btn = QPushButton("⚙️ 高级参数调节")
    owner.advanced_settings_btn.clicked.connect(owner.open_advanced_settings)
    feature_layout.addWidget(owner.advanced_settings_btn)
    feature_group.setLayout(feature_layout)
    layout.addWidget(feature_group)

    stats_group = QGroupBox("6. 统计信息")
    stats_layout = QVBoxLayout()
    owner.stats_text = QTextEdit()
    owner.stats_text.setReadOnly(True)
    owner.stats_text.setMaximumHeight(150)
    stats_layout.addWidget(owner.stats_text)
    stats_group.setLayout(stats_layout)
    layout.addWidget(stats_group)

    layout.addStretch()
    return panel


def create_mapping_display_panel(owner) -> QWidget:
    panel = QWidget()
    layout = QVBoxLayout(panel)
    capture_group = QGroupBox("当前视野 (实时)")
    capture_layout = QVBoxLayout()
    owner.capture_label = QLabel()
    owner.capture_label.setAlignment(Qt.AlignCenter)
    owner.capture_label.setMinimumSize(200, 200)
    owner.capture_label.setStyleSheet("background-color: black;")
    capture_layout.addWidget(owner.capture_label)
    capture_group.setLayout(capture_layout)
    layout.addWidget(capture_group, 1)

    owner.global_group = CollapsibleMapGroup("全局拼接地图 (点击设置导航点)")
    owner.global_map_widget = owner.global_group.scalable_map
    owner.global_map_widget.setStyleSheet("background-color: black;")
    owner.global_map_widget.pixel_clicked.connect(owner.on_map_click)
    layout.addWidget(owner.global_group, 3)
    return panel
