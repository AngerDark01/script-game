import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from auto_modules.ui.modes.poe2_live_terrain.monitor_dialog import Poe2MonitorConfigDialog
from auto_modules.features.poe2.live_terrain.monitor_config import Poe2MonitorConfig


def test_dialog_uses_poe2_config_and_emits_save():
    app = QApplication.instance() or QApplication([])
    dialog = Poe2MonitorConfigDialog(config=Poe2MonitorConfig())
    assert dialog.windowTitle() == "PoE2 监控配置"
    assert dialog.search_radius_spin.value() == 96
    received = []
    dialog.config_saved.connect(received.append)
    dialog.save()
    assert received and isinstance(received[0], Poe2MonitorConfig)
    dialog.deleteLater()
