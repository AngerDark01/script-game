"""Dedicated LAN workspace built on the existing authenticated SyncPanel."""
from pathlib import Path
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from auto_modules.ui.virtual_gamepad.sync_panel import SyncPanel


class LanPage(QWidget):
    def __init__(self, client_factory, parent=None):
        super().__init__(parent)
        self.setObjectName('lanPage')
        self.setStyleSheet('''
        #lanPage { background:#09111f; color:#e7eef8; }
        QFrame[role="hero"] { background:#102238; border:1px solid #294967; border-radius:14px; }
        QLabel[role="eyebrow"] { color:#6fc7ee; font-size:11px; font-weight:700; }
        QLabel[role="muted"] { color:#9aafc4; }
        QScrollArea { border:0; background:transparent; }
        QScrollArea QWidget { background:transparent; }
        QLineEdit, QComboBox, QSpinBox { min-height:34px; padding:0 10px; border:1px solid #29435f; border-radius:7px; background:#0d1a2b; color:#e7eef8; }
        QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border-color:#38bce9; }
        QCheckBox { spacing:8px; color:#b9c9da; min-height:30px; }
        QListWidget { background:#0d1929; border:1px solid #213750; border-radius:9px; padding:5px; }
        QListWidget::item { padding:10px; border-radius:6px; }
        QListWidget::item:selected { background:#174363; color:#f3fbff; }
        QPushButton { min-height:36px; padding:0 14px; border-radius:8px; border:1px solid #2e4967; background:#17283d; color:#e7eef8; }
        QPushButton:hover { background:#203954; border-color:#35b9f2; }
        QFormLayout QLabel { color:#91a8be; }
        ''')
        root = QVBoxLayout(self); root.setContentsMargins(24,20,24,24); root.setSpacing(14)
        hero = QFrame(); hero.setProperty('role','hero'); hl = QHBoxLayout(hero)
        copy = QVBoxLayout(); eyebrow=QLabel('NETWORK CONTROL'); eyebrow.setProperty('role','eyebrow'); copy.addWidget(eyebrow)
        title=QLabel('局域网'); title.setStyleSheet('font-size:26px; font-weight:800;'); copy.addWidget(title)
        subtitle=QLabel('统一管理设备配对、权限和同步通道。键鼠、手柄、位置与事件共用同一连接引擎。'); subtitle.setProperty('role','muted'); subtitle.setWordWrap(True); copy.addWidget(subtitle)
        hl.addLayout(copy, 1); root.addWidget(hero)
        self.panel = SyncPanel(client_factory, parent=self); root.addWidget(self.panel, 1)

    def shutdown(self):
        self.panel.shutdown()
