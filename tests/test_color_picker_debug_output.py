import importlib.util
import unittest
from pathlib import Path


_MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "gui"
    / "dialogs"
    / "color_picker"
    / "debug_output.py"
)
_SPEC = importlib.util.spec_from_file_location("color_picker_debug_output", _MODULE_PATH)
_DEBUG_OUTPUT = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_DEBUG_OUTPUT)

is_wall_preview_debug_enabled = _DEBUG_OUTPUT.is_wall_preview_debug_enabled


class ColorPickerDebugOutputTest(unittest.TestCase):
    def test_wall_preview_debug_is_disabled_by_default(self):
        self.assertFalse(is_wall_preview_debug_enabled({}))

    def test_wall_preview_debug_accepts_explicit_truthy_values(self):
        for value in ("1", "true", "TRUE", "yes", "on"):
            with self.subTest(value=value):
                self.assertTrue(
                    is_wall_preview_debug_enabled(
                        {_DEBUG_OUTPUT.DEBUG_ENV_VAR: value}
                    )
                )

    def test_wall_preview_debug_rejects_non_truthy_values(self):
        for value in ("0", "false", "off", "debug"):
            with self.subTest(value=value):
                self.assertFalse(
                    is_wall_preview_debug_enabled(
                        {_DEBUG_OUTPUT.DEBUG_ENV_VAR: value}
                    )
                )


if __name__ == "__main__":
    unittest.main()
