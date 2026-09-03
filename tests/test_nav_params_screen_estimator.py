import importlib.util
import unittest
from pathlib import Path


_MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "gui"
    / "dialogs"
    / "nav_params"
    / "screen_estimator.py"
)
_SPEC = importlib.util.spec_from_file_location("nav_params_screen_estimator", _MODULE_PATH)
_SCREEN_ESTIMATOR = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_SCREEN_ESTIMATOR)

estimate_click_radii = _SCREEN_ESTIMATOR.estimate_click_radii


class NavParamsScreenEstimatorTest(unittest.TestCase):
    def test_estimates_click_radii_from_center_and_bounds(self):
        estimate = estimate_click_radii((500, 400), (0, 0, 1000, 800))

        self.assertEqual(estimate.min_radius, 154)
        self.assertEqual(estimate.max_radius, 280)

    def test_clamps_small_screens_to_minimums(self):
        estimate = estimate_click_radii((100, 100), (0, 0, 200, 200))

        self.assertEqual(estimate.min_radius, 120)
        self.assertEqual(estimate.max_radius, 180)

    def test_clamps_large_screens_to_maximum(self):
        estimate = estimate_click_radii((2000, 1500), (0, 0, 4000, 3000))

        self.assertEqual(estimate.min_radius, 495)
        self.assertEqual(estimate.max_radius, 900)

    def test_returns_none_when_center_is_outside_bounds(self):
        self.assertIsNone(estimate_click_radii((1200, 400), (0, 0, 1000, 800)))


if __name__ == "__main__":
    unittest.main()
