import importlib.util
import tempfile
import unittest
from datetime import datetime
from pathlib import Path


_MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "gui"
    / "dialogs"
    / "advanced_settings"
    / "file_io.py"
)
_SPEC = importlib.util.spec_from_file_location("advanced_settings_file_io", _MODULE_PATH)
_FILE_IO = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_FILE_IO)

format_params_for_display = _FILE_IO.format_params_for_display
load_params_snapshot = _FILE_IO.load_params_snapshot
save_params_snapshot = _FILE_IO.save_params_snapshot


class AdvancedSettingsFileIoTest(unittest.TestCase):
    def test_save_params_snapshot_uses_explicit_directory_and_safe_filename(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            saved_path = save_params_snapshot(
                "bad/name",
                {"edge_low": 50},
                output_dir=temp_dir,
                now=datetime(2026, 5, 26, 16, 40, 0),
            )

            self.assertEqual(Path(temp_dir), saved_path.parent)
            self.assertEqual("params_bad_name_20260526_164000.json", saved_path.name)

            payload = load_params_snapshot(saved_path)

            self.assertEqual(payload["name"], "bad/name")
            self.assertEqual(payload["timestamp"], "2026-05-26T16:40:00")
            self.assertEqual(payload["parameters"], {"edge_low": 50})

    def test_load_params_snapshot_rejects_files_without_parameters_object(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            invalid_path = Path(temp_dir) / "invalid.json"
            invalid_path.write_text('{"parameters": []}', encoding="utf-8")

            with self.assertRaises(ValueError):
                load_params_snapshot(invalid_path)

    def test_format_params_for_display_keeps_non_ascii_text(self):
        display = format_params_for_display({"name": "中文"})

        self.assertIn('"中文"', display)


if __name__ == "__main__":
    unittest.main()
