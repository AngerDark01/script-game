import unittest
from types import SimpleNamespace

import numpy as np

from auto_modules.core.localization import LocalizationResult
from auto_modules.ui.modes.navigation.runtime.localization_tick import capture_navigation_localization_tick


class _ScreenCapture:
    def __init__(self, frame):
        self.frame = frame
        self.calls = []

    def capture(self, left, top, width, height):
        self.calls.append((left, top, width, height))
        return self.frame


class _NavigationCore:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def localize_result(self, frame, *, player_pos=None):
        self.calls.append((frame, player_pos))
        return self.result


class NavigationLocalizationTickTests(unittest.TestCase):
    def test_tick_returns_the_core_typed_result_without_gui_conversion(self):
        frame = np.zeros((12, 16, 3), dtype=np.uint8)
        result = LocalizationResult(
            position=(120.0, 80.0),
            confidence=0.9,
            source="f2f",
            registration_valid=True,
        )
        capture = _ScreenCapture(frame)
        nav_core = _NavigationCore(result)
        nav_config = SimpleNamespace(
            monitor_logical_center=(500, 400),
            monitor_region=None,
            monitor_size=16,
        )

        tick = capture_navigation_localization_tick(
            build_capture_geometry=lambda: (
                {"left": 10, "top": 20, "width": 16, "height": 12},
                (8, 6),
            ),
            screen_capture=capture,
            nav_config=nav_config,
            nav_core=nav_core,
            tracker=None,
            previous_player_local_pos=None,
        )

        self.assertEqual([(10, 20, 16, 12)], capture.calls)
        self.assertEqual([(frame, (8, 6))], nav_core.calls)
        self.assertIs(result, tick.localization)
        self.assertEqual((120.0, 80.0), tick.localization.localized_pos)


if __name__ == "__main__":
    unittest.main()
