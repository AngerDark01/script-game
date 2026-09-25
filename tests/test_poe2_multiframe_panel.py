from auto_modules.ui.modes.poe2_live_terrain.multiframe_panel import Poe2MultiframePanel
from PySide6.QtWidgets import QApplication


def test_multiframe_panel_exposes_controls_and_state():
    app = QApplication.instance() or QApplication([])
    panel = Poe2MultiframePanel()
    panel.set_running(True)
    assert not panel.start_button.isEnabled()
    assert panel.stop_button.isEnabled()
    panel.set_state(status="collecting", evidence_version=2, recovery_revision=1, reason="moving", position=(1, 2))
    assert "collecting" in panel.status_label.text()
    assert "(1, 2)" in panel.position_label.text()
    assert panel.selected_strategies() == (True, True)
    panel.set_archive_available(True)
    assert panel.save_button.isEnabled()
