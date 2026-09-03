from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget


def build_map_selector_bar(owner) -> QWidget:
    """Create map selection controls and compact-layout entry."""
    bar = _toolbar_widget()
    layout = bar.layout()

    owner.map_combo = QComboBox()
    owner.refresh_map_list()
    layout.addWidget(QLabel("选择地图:"))
    layout.addWidget(owner.map_combo, 1)

    owner.btn_load = QPushButton("加载地图")
    owner.btn_load.setProperty("role", "primary")
    layout.addWidget(owner.btn_load)

    owner.compact_mode_button = QPushButton("完整布局")
    owner.compact_mode_button.setToolTip("切换导航页小窗/完整布局")
    layout.addWidget(owner.compact_mode_button)
    return bar


def build_navigation_actions_bar(owner) -> QWidget:
    """Create primary navigation commands that stay visible in compact mode."""
    bar = _toolbar_widget()
    layout = bar.layout()

    owner.btn_hint = QPushButton("设置起点")
    owner.btn_hint.setCheckable(True)
    owner.btn_hint.setEnabled(False)
    layout.addWidget(owner.btn_hint)

    owner.btn_start = QPushButton("开始定位")
    owner.btn_start.setCheckable(True)
    owner.btn_start.setEnabled(False)
    layout.addWidget(owner.btn_start)

    owner.btn_auto_nav = QPushButton("自动到出口")
    owner.btn_auto_nav.setCheckable(True)
    owner.btn_auto_nav.setEnabled(False)
    owner.btn_auto_nav.setProperty("role", "success")
    layout.addWidget(owner.btn_auto_nav)

    owner.event_button = QPushButton("事件管理")
    layout.addWidget(owner.event_button)

    owner.params_button = QPushButton("参数面板")
    layout.addWidget(owner.params_button)

    owner.compact_more_button = QPushButton("更多")
    owner.compact_more_button.setToolTip("打开路线、事件、参数和地图工具")
    layout.addWidget(owner.compact_more_button)

    layout.addStretch(1)
    return bar


def build_route_tools_bar(owner) -> QWidget:
    """Create route-editing commands that can collapse in compact mode."""
    bar = _toolbar_widget()
    layout = bar.layout()

    owner.btn_set_exit = QPushButton("设置出口")
    owner.btn_set_exit.setCheckable(True)
    owner.btn_set_exit.setEnabled(False)
    layout.addWidget(owner.btn_set_exit)

    owner.btn_add_required = QPushButton("添加必经点")
    owner.btn_add_required.setCheckable(True)
    owner.btn_add_required.setEnabled(False)
    layout.addWidget(owner.btn_add_required)

    owner.btn_undo_required = QPushButton("撤销必经点")
    owner.btn_undo_required.setEnabled(False)
    layout.addWidget(owner.btn_undo_required)

    owner.btn_add_guide = QPushButton("添加途经点")
    owner.btn_add_guide.setCheckable(True)
    owner.btn_add_guide.setEnabled(False)
    layout.addWidget(owner.btn_add_guide)

    owner.btn_undo_guide = QPushButton("撤销途经点")
    owner.btn_undo_guide.setEnabled(False)
    layout.addWidget(owner.btn_undo_guide)

    owner.btn_clear_route = QPushButton("清空路线")
    owner.btn_clear_route.setEnabled(False)
    owner.btn_clear_route.setProperty("role", "danger")
    layout.addWidget(owner.btn_clear_route)

    owner.btn_save_route = QPushButton("保存路线")
    owner.btn_save_route.setEnabled(False)
    owner.btn_save_route.setProperty("role", "success")
    layout.addWidget(owner.btn_save_route)

    layout.addStretch(1)
    return bar


def build_utility_bar(owner) -> QWidget:
    """Create secondary utility commands for calibration and sample capture."""
    bar = _toolbar_widget()
    layout = bar.layout()

    owner.route_tools_button = QPushButton("路线工具")
    owner.route_tools_button.setCheckable(True)
    owner.route_tools_button.setToolTip("在小窗模式下显示或隐藏路线编辑工具")
    layout.addWidget(owner.route_tools_button)

    owner.calibrate_button = QPushButton("校准屏幕中心")
    layout.addWidget(owner.calibrate_button)

    owner.sample_window_button = QPushButton("截图窗口")
    owner.sample_window_button.setEnabled(False)
    layout.addWidget(owner.sample_window_button)

    owner.save_minimap_sample_button = QPushButton("保存小地图样本")
    owner.save_minimap_sample_button.setEnabled(False)
    layout.addWidget(owner.save_minimap_sample_button)

    owner.map_zoom_out_button = QPushButton("地图-")
    owner.map_zoom_out_button.setToolTip("缩小中间地图显示")
    layout.addWidget(owner.map_zoom_out_button)

    owner.map_fit_button = QPushButton("适应地图")
    owner.map_fit_button.setToolTip("按当前窗口大小重新适应中间地图")
    layout.addWidget(owner.map_fit_button)

    owner.map_zoom_in_button = QPushButton("地图+")
    owner.map_zoom_in_button.setToolTip("放大中间地图显示")
    layout.addWidget(owner.map_zoom_in_button)

    layout.addStretch(1)
    return bar


def _toolbar_widget() -> QWidget:
    widget = QWidget()
    widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    widget.setMinimumHeight(40)
    widget.setMaximumHeight(40)
    layout = QHBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    return widget
