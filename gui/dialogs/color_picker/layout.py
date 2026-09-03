from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QTextEdit,
    QVBoxLayout,
)

from ...widgets.clickable_label import ClickableImageLabel


def build_color_picker_ui(dialog) -> None:
    """Build the color picker dialog UI and attach stable widget attributes."""
    layout = QVBoxLayout(dialog)
    layout.addWidget(_create_help_label())
    layout.addLayout(_create_mode_buttons(dialog))
    layout.addLayout(_create_image_panels(dialog))
    layout.addWidget(_create_result_group(dialog))
    layout.addLayout(_create_footer(dialog))
    dialog.set_mode("wall")


def _create_help_label() -> QLabel:
    help_label = QLabel(
        "INFO: 使用说明：\n"
        "1. 点击「选择墙体」，在左侧图像上点击墙体区域（建议5-10个点，覆盖不同亮度）\n"
        "2. 点击「选择人物」，在左侧图像上点击人物标记（1-2个点）\n"
        "3. 点击「计算HSV范围」，系统自动计算颜色范围\n"
        "4. 查看右侧二值化预览效果，满意后点击「确定」"
    )
    help_label.setWordWrap(True)
    help_label.setStyleSheet("background-color: #2c3e50; color: white; padding: 10px; border-radius: 5px;")
    return help_label


def _create_mode_buttons(dialog) -> QHBoxLayout:
    btn_layout = QHBoxLayout()
    dialog.wall_mode_btn = QPushButton("[BLUE] 选择墙体")
    dialog.wall_mode_btn.setStyleSheet("padding: 10px; font-size: 14px;")
    dialog.wall_mode_btn.clicked.connect(lambda: dialog.set_mode("wall"))
    btn_layout.addWidget(dialog.wall_mode_btn)

    dialog.player_mode_btn = QPushButton("[GREEN] 选择人物")
    dialog.player_mode_btn.setStyleSheet("padding: 10px; font-size: 14px;")
    dialog.player_mode_btn.clicked.connect(lambda: dialog.set_mode("player"))
    btn_layout.addWidget(dialog.player_mode_btn)

    dialog.calc_btn = QPushButton("[ZOOM] 计算HSV范围")
    dialog.calc_btn.setStyleSheet("padding: 10px; font-size: 14px; background-color: #e74c3c; color: white;")
    dialog.calc_btn.clicked.connect(dialog.calculate_hsv_ranges)
    btn_layout.addWidget(dialog.calc_btn)

    dialog.reset_btn = QPushButton("[REFRESH] 重置")
    dialog.reset_btn.setStyleSheet("padding: 10px; font-size: 14px;")
    dialog.reset_btn.clicked.connect(dialog.reset_selection)
    btn_layout.addWidget(dialog.reset_btn)
    return btn_layout


def _create_image_panels(dialog) -> QHBoxLayout:
    main_layout = QHBoxLayout()
    main_layout.addWidget(_create_source_group(dialog), 1)
    main_layout.addWidget(_create_preview_group(dialog), 1)
    return main_layout


def _create_source_group(dialog) -> QGroupBox:
    left_group = QGroupBox("原图（点击选择颜色）")
    left_layout = QVBoxLayout(left_group)

    zoom_layout = QHBoxLayout()
    dialog.zoom_slider = QSlider(Qt.Horizontal)
    dialog.zoom_slider.setRange(50, 400)
    dialog.zoom_slider.setValue(100)
    dialog.zoom_slider.valueChanged.connect(dialog.on_zoom_changed)
    zoom_layout.addWidget(QLabel("缩放"))
    zoom_layout.addWidget(dialog.zoom_slider)
    dialog.zoom_value_label = QLabel("100%")
    zoom_layout.addWidget(dialog.zoom_value_label)
    left_layout.addLayout(zoom_layout)

    dialog.scroll_area = QScrollArea()
    dialog.scroll_area.setWidgetResizable(True)
    dialog.image_label = ClickableImageLabel(dialog.original_width, dialog.original_height)
    dialog.image_label.setStyleSheet("background-color: black; border: 2px solid #3498db;")
    dialog.image_label.setAlignment(Qt.AlignCenter)
    dialog.image_label.pixel_clicked.connect(dialog.on_pixel_clicked)
    dialog.image_label.wheel_zoom.connect(dialog.on_wheel_zoom)
    dialog.scroll_area.setWidget(dialog.image_label)
    left_layout.addWidget(dialog.scroll_area)
    return left_group


def _create_preview_group(dialog) -> QGroupBox:
    right_group = QGroupBox("二值化预览")
    right_layout = QVBoxLayout(right_group)
    dialog.preview_label = QLabel()
    dialog.preview_label.setMinimumSize(400, 400)
    dialog.preview_label.setStyleSheet("background-color: black; border: 2px solid #2ecc71;")
    dialog.preview_label.setAlignment(Qt.AlignCenter)
    right_layout.addWidget(dialog.preview_label)
    return right_group


def _create_result_group(dialog) -> QGroupBox:
    result_group = QGroupBox("计算结果")
    result_layout = QVBoxLayout(result_group)
    dialog.result_text = QTextEdit()
    dialog.result_text.setReadOnly(True)
    dialog.result_text.setMaximumHeight(120)
    dialog.result_text.setStyleSheet("font-family: Consolas, monospace; font-size: 12px;")
    result_layout.addWidget(dialog.result_text)
    return result_group


def _create_footer(dialog) -> QHBoxLayout:
    footer_layout = QHBoxLayout()
    dialog.ok_btn = QPushButton("[OK] 确定")
    dialog.ok_btn.setStyleSheet("padding: 10px; font-size: 14px; background-color: #27ae60; color: white;")
    dialog.ok_btn.clicked.connect(dialog.accept)
    dialog.ok_btn.setEnabled(False)
    footer_layout.addWidget(dialog.ok_btn)

    dialog.cancel_btn = QPushButton("[CANCEL] 取消")
    dialog.cancel_btn.setStyleSheet("padding: 10px; font-size: 14px;")
    dialog.cancel_btn.clicked.connect(dialog.reject)
    footer_layout.addWidget(dialog.cancel_btn)
    return footer_layout
