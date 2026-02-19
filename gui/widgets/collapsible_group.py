
from PySide6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QPushButton
)

from .scalable_map import ScalableMapWidget

class CollapsibleMapGroup(QGroupBox):
    """
    可收缩的地图组组件
    """

    def __init__(self, title="全局拼接地图 (点击设置导航点)", parent=None):
        super().__init__(title, parent)

        self.setCheckable(True)
        self.setChecked(True)

        self.main_layout = QVBoxLayout(self)
        self.scalable_map = ScalableMapWidget()
        self.controls_layout = QHBoxLayout()

        self.zoom_in_btn = QPushButton("🔍+")
        self.zoom_in_btn.clicked.connect(self.scalable_map.zoom_in)
        self.zoom_in_btn.setToolTip("放大 (Ctrl+滚轮向上)")

        self.zoom_out_btn = QPushButton("🔍-")
        self.zoom_out_btn.clicked.connect(self.scalable_map.zoom_out)
        self.zoom_out_btn.setToolTip("缩小 (Ctrl+滚轮向下)")

        self.reset_zoom_btn = QPushButton("🔄")
        self.reset_zoom_btn.clicked.connect(self.scalable_map.reset_zoom)
        self.reset_zoom_btn.setToolTip("重置缩放")

        self.controls_layout.addWidget(self.zoom_in_btn)
        self.controls_layout.addWidget(self.zoom_out_btn)
        self.controls_layout.addWidget(self.reset_zoom_btn)
        self.controls_layout.addStretch()

        self.main_layout.addLayout(self.controls_layout)
        self.main_layout.addWidget(self.scalable_map)

        self.toggled.connect(self._on_toggled)

    def set_map_image(self, pixmap):
        self.scalable_map.set_image(pixmap)

    def _on_toggled(self, checked):
        self.scalable_map.setVisible(checked)
        self.controls_layout.parentWidget().setVisible(checked)
