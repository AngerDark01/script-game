import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.runtime_paths import data_root


class RuntimePathTests(unittest.TestCase):
    def test_development_root_is_unchanged(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(data_root(Path('.')), Path('.').resolve())

    def test_packaged_data_root_handles_spaces_and_unicode(self):
        with tempfile.TemporaryDirectory(prefix='运行 数据 ') as temporary:
            with patch.dict(os.environ, {'AUTO_MODULES_DATA_DIR': temporary}):
                self.assertEqual(data_root(Path('irrelevant')), Path(temporary).resolve())

    def test_installed_paths_use_data_root_but_assets_keep_source_root(self):
        from gui.composition.paths import map_data_dir_from_file, root_config_path_from_file, advanced_settings_dir_from_file, project_root_from_file
        with tempfile.TemporaryDirectory() as temporary:
            with patch.dict(os.environ, {'AUTO_MODULES_DATA_DIR': temporary}):
                source = Path(__file__)
                self.assertEqual(map_data_dir_from_file(source), Path(temporary) / 'map_data')
                self.assertEqual(root_config_path_from_file(source), Path(temporary) / 'config.json')
                self.assertEqual(advanced_settings_dir_from_file(source), Path(temporary) / 'configs' / 'advanced_settings')
                self.assertEqual(project_root_from_file(source), source.resolve().parents[1])

    def test_packaged_host_prefers_self_contained_executable(self):
        from gui.gamepad.host_manager import GamepadHostManager
        with tempfile.TemporaryDirectory(prefix='host 空格 ') as temporary:
            host = Path(temporary) / 'VirtualGamepadHost.exe'
            host.touch()
            with patch.dict(os.environ, {'AUTO_MODULES_HOST_DIR': temporary}):
                self.assertEqual(GamepadHostManager._default_host_directory(), Path(temporary))
                self.assertEqual(GamepadHostManager._default_host_command(), [str(host)])

    def test_loot_diagnostics_are_user_data(self):
        from core.events.types.loot.diagnostics import LootDiagnosticCapture
        with tempfile.TemporaryDirectory() as temporary:
            with patch.dict(os.environ, {'AUTO_MODULES_DATA_DIR': temporary}):
                self.assertTrue(LootDiagnosticCapture().output_dir.is_relative_to(Path(temporary)))
