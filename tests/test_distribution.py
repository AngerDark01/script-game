import tempfile
import unittest
from pathlib import Path
import importlib.util

_BUILD_PATH = Path(__file__).resolve().parents[1] / "packaging" / "distribution" / "build.py"
_SPEC = importlib.util.spec_from_file_location("auto_modules_distribution_build", _BUILD_PATH)
_BUILD = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(_BUILD)
safe_destination = _BUILD.safe_destination
select_runtime_sources = _BUILD.select_runtime_sources
sanitize_config = _BUILD.sanitize_config
dependency_closure = _BUILD.dependency_closure
ROOT_REQUIREMENTS = _BUILD.ROOT_REQUIREMENTS
copy_native_runtime = _BUILD.copy_native_runtime


class DistributionTests(unittest.TestCase):
    def test_rejects_escape_and_absolute_archive_paths(self):
        base = Path(tempfile.gettempdir())
        for name in ('../escape', '/absolute', 'C:/escape', 'a/../../escape'):
            with self.assertRaises(ValueError):
                safe_destination(base, name)
        self.assertEqual(safe_destination(base, 'good/file'), base / 'good' / 'file')

    def test_source_allowlist_excludes_local_secrets_and_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            for name in ('main.py', 'src/auto_modules/ui/view.py', 'src/auto_modules/ui/__pycache__/view.pyc', 'src/auto_modules/ui/.env', 'src/auto_modules/core/code.py',
                         'config.json', 'logs/session.log', '.git/config', 'data/virtual_gamepad/configs/controller-1.json',
                         'src/auto_modules/ui/virtual_gamepad/main.py', 'resources/assets/perception_models/model.onnx'):
                path = base / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
            selected = {p.relative_to(base).as_posix() for p in select_runtime_sources(base)}
            self.assertEqual(selected, {'main.py', 'src/auto_modules/ui/view.py', 'src/auto_modules/core/code.py',
                                       'src/auto_modules/ui/virtual_gamepad/main.py', 'resources/assets/perception_models/model.onnx'})

    def test_config_templates_drop_credentials_and_capture_coordinates(self):
        result = sanitize_config({'api_key': 'secret', 'nested': {'password': 'secret', 'value': 2}, 'monitor_region': [1,2,3,4], 'monitor_logical_center': [2,3]})
        self.assertNotIn('api_key', result)
        self.assertEqual(result['nested'], {'value': 2})
        self.assertIsNone(result['monitor_region'])
        self.assertIsNone(result['monitor_logical_center'])

    def test_dependency_selection_excludes_unrelated_editable_project(self):
        names = {d.metadata['Name'].lower() for d in dependency_closure(ROOT_REQUIREMENTS)}
        self.assertIn('shiboken6', names)
        self.assertIn('onnxruntime', names)
        self.assertNotIn('mihomo', names)
        self.assertNotIn('openai', names)
        self.assertNotIn('pyside6_addons', names)

    def test_native_runtime_is_app_local_and_keeps_cpython_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            python = Path(directory)
            qt = python / 'Lib/site-packages/PySide6'
            qt.mkdir(parents=True)
            for name in ('msvcp140.dll', 'msvcp140_1.dll', 'vcruntime140.dll', 'vcruntime140_1.dll'):
                (qt / name).write_bytes(b'wheel-runtime')
            (python / 'vcruntime140.dll').write_bytes(b'cpython-runtime')
            manifest = copy_native_runtime(python)
            self.assertEqual((python / 'msvcp140.dll').read_bytes(), b'wheel-runtime')
            self.assertEqual((python / 'vcruntime140.dll').read_bytes(), b'cpython-runtime')
            self.assertNotIn('vcruntime140.dll', manifest)
