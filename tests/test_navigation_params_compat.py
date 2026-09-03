import importlib.util
import unittest
from pathlib import Path


_MODULE_PATH = Path(__file__).resolve().parents[1] / "gui" / "navigation_params.py"
_SPEC = importlib.util.spec_from_file_location("navigation_params_module", _MODULE_PATH)
_NAV_PARAMS = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_NAV_PARAMS)

NavConfig = _NAV_PARAMS.NavConfig


class NavigationParamsCompatTest(unittest.TestCase):
    def test_legacy_nav_preferences_round_trip(self):
        config = NavConfig.from_dict(
            {
                "nav_preferences": {
                    "k_ratio": 7.5,
                    "y_bias": 2.5,
                }
            }
        )

        payload = config.to_dict()

        self.assertEqual(config.nav_preferences.k_ratio, 7.5)
        self.assertEqual(config.nav_preferences.y_bias, 2.5)
        self.assertEqual(
            payload["nav_preferences"],
            {
                "k_ratio": 7.5,
                "y_bias": 2.5,
            },
        )


if __name__ == "__main__":
    unittest.main()
