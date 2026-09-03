import importlib.util
import sys
import types
import unittest
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[1]
_PACKAGE_NAME = "advanced_settings_test_pkg"
_PACKAGE = types.ModuleType(_PACKAGE_NAME)
_PACKAGE.__path__ = [str(_ROOT / "gui" / "dialogs" / "advanced_settings")]
sys.modules[_PACKAGE_NAME] = _PACKAGE


def _load_module(module_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(
        f"{_PACKAGE_NAME}.{module_name}",
        _ROOT / "gui" / "dialogs" / "advanced_settings" / filename,
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_PRESETS = _load_module("presets", "presets.py")
_PARAMS_ADAPTER = _load_module("params_adapter", "params_adapter.py")


class FakeValueWidget:
    def __init__(self):
        self.value = None

    def setValue(self, value):
        self.value = value


class FakeCheckWidget:
    def __init__(self):
        self.checked = None

    def setChecked(self, value):
        self.checked = value


class FakeDialog:
    def __init__(self):
        for name in {
            "contrast_factor_spin",
            "blue_boost_spin",
            "edge_low_spin",
            "edge_high_spin",
            "wall_weight_spin",
            "edge_weight_spin",
            "gray_weight_spin",
            "clahe_clip_spin",
            "gamma_value_spin",
            "tophat_kernel_spin",
            "tophat_strength_spin",
            "clahe_grid_spin",
            "sat_thresh_spin",
            "sat_radius_spin",
            "trans_wall_thresh_spin",
            "trans_sat_penalty_spin",
            "conf_thresh_spin",
            "keyframe_thresh_spin",
            "weight_add_spin",
            "weight_cap_spin",
        }:
            setattr(self, name, FakeValueWidget())

        for name in {
            "deepen_enabled_check",
            "gamma_enabled_check",
            "tophat_enabled_check",
            "clahe_enabled_check",
            "sat_filter_check",
            "transparent_mode_check",
        }:
            setattr(self, name, FakeCheckWidget())


class AdvancedSettingsPresetsTest(unittest.TestCase):
    def test_preset_names_keep_existing_ui_order(self):
        self.assertEqual(
            _PRESETS.preset_names(),
            (
                "默认参数",
                "流放之路优化",
                "火炬之光优化",
                "高对比度模式",
                "低对比度模式",
            ),
        )

    def test_preset_values_are_data_only(self):
        self.assertEqual(
            dict(_PRESETS.preset_values("流放之路优化")),
            {
                "contrast_factor_spin": 1.3,
                "blue_boost_spin": 1.2,
                "edge_low_spin": 40,
                "edge_high_spin": 120,
                "wall_weight_spin": 60,
                "edge_weight_spin": 25,
                "gray_weight_spin": 15,
            },
        )

    def test_apply_preset_to_widgets_uses_preset_data(self):
        dialog = FakeDialog()

        applied = _PARAMS_ADAPTER.apply_preset_to_widgets(dialog, "高对比度模式")

        self.assertTrue(applied)
        self.assertEqual(dialog.contrast_factor_spin.value, 1.5)
        self.assertEqual(dialog.blue_boost_spin.value, 1.3)
        self.assertEqual(dialog.clahe_clip_spin.value, 3.0)

    def test_default_preset_still_resets_widgets(self):
        dialog = FakeDialog()

        applied = _PARAMS_ADAPTER.apply_preset_to_widgets(dialog, "默认参数")

        self.assertTrue(applied)
        self.assertEqual(dialog.contrast_factor_spin.value, 1.2)
        self.assertTrue(dialog.deepen_enabled_check.checked)

    def test_unknown_preset_returns_false(self):
        dialog = FakeDialog()

        self.assertFalse(_PARAMS_ADAPTER.apply_preset_to_widgets(dialog, "unknown"))


if __name__ == "__main__":
    unittest.main()
