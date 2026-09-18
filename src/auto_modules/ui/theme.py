"""Centralized visual tokens and Qt stylesheet for the desktop UI."""

COLORS = {
    "window": "#0B1220",
    "surface": "#111C2B",
    "canvas": "#071019",
    "border": "#26364A",
    "text": "#E5EEF7",
    "muted": "#91A4B8",
    "primary": "#38BDF8",
    "success": "#22C55E",
    "warning": "#F59E0B",
    "danger": "#EF4444",
}


def app_stylesheet() -> str:
    """Return the application-wide dark tactical palette."""
    return """
    QWidget {
        color: #E5EEF7;
        background: #0B1220;
        font-size: 13px;
    }
    QMainWindow, QStackedWidget {
        background: #0B1220;
    }
    QFrame[role="surface"], QGroupBox {
        background: #111C2B;
        border: 1px solid #26364A;
        border-radius: 8px;
    }
    QGroupBox {
        margin-top: 10px;
        padding: 12px 8px 8px 8px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 5px;
        color: #91A4B8;
    }
    QPushButton, QToolButton {
        min-height: 34px;
        padding: 0 12px;
        border: 1px solid #33465C;
        border-radius: 6px;
        background: #172538;
    }
    QPushButton:hover, QToolButton:hover {
        border-color: #38BDF8;
        background: #1D344B;
    }
    QPushButton:checked, QPushButton[role="primary"], QToolButton:checked {
        color: #06131D;
        background: #38BDF8;
        border-color: #7DD3FC;
    }
    QPushButton[role="mode"] {
        min-height: 36px;
        padding: 0 14px;
        background: #111A27;
    }
    QPushButton[role="mode"]:checked {
        color: #06131D;
        background: #38BDF8;
        border-color: #7DD3FC;
    }
    QPushButton[role="success"] {
        color: #06140B;
        background: #22C55E;
        border-color: #86EFAC;
    }
    QPushButton[role="warning"] {
        color: #1C1200;
        background: #F59E0B;
        border-color: #FCD34D;
    }
    QPushButton[role="danger"] {
        color: #FFF1F2;
        background: #7F1D1D;
        border-color: #EF4444;
    }
    QPushButton:disabled, QToolButton:disabled {
        color: #66788D;
        background: #111A27;
        border-color: #243244;
    }
    QComboBox, QSpinBox, QDoubleSpinBox {
        min-height: 34px;
        background: #0F1A28;
        border: 1px solid #33465C;
        border-radius: 6px;
        padding: 0 8px;
    }
    QComboBox QAbstractItemView {
        background: #111C2B;
        color: #E5EEF7;
        selection-background-color: #0E7490;
    }
    QLabel[role="muted"] { color: #91A4B8; }
    QFrame[role="status"] {
        padding: 5px 9px;
        background: #111C2B;
        border: 1px solid #26364A;
        border-radius: 6px;
    }
    QLabel[role="status-value"] { color: #E5EEF7; font-weight: 500; }
    QGraphicsView {
        background: #071019;
        border: 1px solid #26364A;
        border-radius: 8px;
    }
    QFrame[role="empty-state"] {
        background: #111C2B;
        border: 1px solid #38516B;
        border-radius: 10px;
    }
    QLabel[role="empty-title"] {
        color: #E5EEF7;
        font-size: 16px;
        font-weight: 500;
    }
    QFrame[role="map-legend"] {
        background: rgba(17, 28, 43, 235);
        border: 1px solid #38516B;
        border-radius: 6px;
    }
    QMenu {
        background: #111C2B;
        color: #E5EEF7;
        border: 1px solid #33465C;
    }
    QMenu::item:selected {
        background: #0E7490;
    }
    QScrollBar:vertical, QScrollBar:horizontal {
        background: #0B1220;
        border: none;
    }
    """
