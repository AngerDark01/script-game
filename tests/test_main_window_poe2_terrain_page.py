import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from auto_modules.features.poe2.live_terrain import TerrainSessionState
from auto_modules.ui.main_window import MainWindow
from auto_modules.ui.modes.poe2_live_terrain import Poe2LiveTerrainPage
from tests.gamepad_test_support import InertGamepadHostManager


class _FakeTerrainService:
    state = TerrainSessionState.NEW

    def initialize(self):
        self.state = TerrainSessionState.READY_TO_CAPTURE

    def capture(self):
        raise RuntimeError("not in this UI composition test")

    def reset(self):
        self.state = TerrainSessionState.NEW

    def snapshot(self):
        return None


class MainWindowPoe2TerrainPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_new_page_is_appended_without_changing_existing_page_indices(self):
        test_service = _FakeTerrainService()
        multiframe_factory = object()

        class _Archive:
            root = None

        with patch(
            "auto_modules.ui.main_window.build_poe2_live_terrain_composition",
            return_value=SimpleNamespace(
                service=_FakeTerrainService(),
                runtime=None,
                config_store=None,
                capture_test_service=test_service,
                capture_test_archive=_Archive(),
                capture_preview=lambda _config: None,
                capture_recognizer=None,
                multiframe_localization_factory=multiframe_factory,
            ),
        ):
            window = MainWindow(gamepad_host_manager=InertGamepadHostManager())
        try:
            self.assertEqual(7, window.stacked_widget.indexOf(window.poe2_terrain_page))
            self.assertIsInstance(window.poe2_terrain_page, Poe2LiveTerrainPage)
            self.assertEqual(window.poe2_terrain_page.tabs.count(), 2)
            self.assertIs(window.poe2_terrain_page.multiframe_localization_factory, multiframe_factory)
            self.assertIs(
                window.poe2_terrain_page.capture_test_page.multiframe_localization_factory,
                multiframe_factory,
            )
            window.switch_mode(7)
            self.assertIs(window.stacked_widget.currentWidget(), window.poe2_terrain_page)
            self.assertTrue(window.mode_btn_poe2_terrain.isChecked())
            self.assertEqual(0, window.stacked_widget.indexOf(window.mapping_widget))
            self.assertEqual(2, window.stacked_widget.indexOf(window.gamepad_page))
        finally:
            window.close()
            self.app.processEvents()
            window.deleteLater()
