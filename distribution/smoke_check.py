"""Offline installed-runtime smoke test. Does not attach to a real host or hook input."""
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
sys.dont_write_bytecode = True
ROOT = Path(sys.executable).resolve().parent.parent / 'app'

# Import ONNX before Qt: Qt otherwise masks missing app-local MSVC dependencies.
import onnxruntime
import ctypes
kernel = ctypes.WinDLL('kernel32', use_last_error=True)
kernel.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
kernel.GetModuleHandleW.restype = ctypes.c_void_p
kernel.GetModuleFileNameW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint]
kernel.GetModuleFileNameW.restype = ctypes.c_uint
for dll in ('msvcp140.dll', 'msvcp140_1.dll', 'vcruntime140.dll', 'vcruntime140_1.dll'):
    handle = kernel.GetModuleHandleW(dll)
    assert handle, f'Native runtime not loaded: {dll}'
    buffer = ctypes.create_unicode_buffer(32768)
    assert kernel.GetModuleFileNameW(handle, buffer, len(buffer))
    assert Path(buffer.value).resolve().is_relative_to(ROOT.parent), f'External native runtime: {buffer.value}'
    print('APP_LOCAL_RUNTIME', dll, buffer.value)

with tempfile.TemporaryDirectory(prefix='auto_modules_smoke_') as temporary:
    os.environ['AUTO_MODULES_DATA_DIR'] = temporary
    modules = ['numpy', 'cv2', 'PySide6.QtWidgets', 'mss', 'pydirectinput', 'onnxruntime', 'rapidocr_onnxruntime',
               'core.actions', 'core.localization.navigation_core', 'gui.main_window', 'gui.modes.map_editor.widget',
               'gui.dialogs.perception', 'gui.gamepad.host_manager']
    for name in modules:
        importlib.import_module(name)
    from PySide6.QtWidgets import QApplication
    from virtual_gamepad.ui.virtual_gamepad_ui.gamepad_page import GamepadPage
    from gui.composition.paths import map_data_dir_from_file
    from core.perception.providers.rapidocr_models import list_rapidocr_model_specs, verify_rapidocr_model_file
    import numpy as np
    from rapidocr_onnxruntime import RapidOCR
    from gui.main_window import MainWindow
    from gui.gamepad.host_manager import HostStartResult

    class OfflineHost:
        def start(self): return HostStartResult(False, False, 'Offline smoke; real driver not touched')
        def create_client(self):
            from virtual_gamepad.client.python import VirtualGamepadClient
            return VirtualGamepadClient()

    # Build the full UI without a host. Do not pump events that could poll a real pipe.
    app = QApplication.instance() or QApplication([])
    window = MainWindow(gamepad_host_manager=OfflineHost())
    assert window.gamepad_page.sync_panel is not None
    window.gamepad_page._timer.stop()
    window.gamepad_page.sync_panel._timer.stop()
    assert map_data_dir_from_file(ROOT / 'main.py') == Path(temporary) / 'map_data'
    specs = list_rapidocr_model_specs()
    for spec in specs:
        model_path = ROOT / 'assets' / 'perception_models' / spec.file_name
        verify_rapidocr_model_file(spec, model_path)
    engine = RapidOCR(intra_op_num_threads=1, inter_op_num_threads=1)
    engine(np.full((80, 240, 3), 255, dtype=np.uint8))
    assert sys.flags.isolated == 1, 'Embedded interpreter must be isolated'
    payload = ROOT.parent
    assert all(Path(item).resolve().is_relative_to(payload) for item in sys.path), 'External Python path leaked into embedded runtime'
    print(json.dumps({'ok': True, 'python': sys.version, 'executable': sys.executable,
                      'sys_path': sys.path, 'imports': modules, 'ocr': 'blank-frame inference passed',
                      'ui': 'full workbench including sync tab constructed'}, ensure_ascii=False))
