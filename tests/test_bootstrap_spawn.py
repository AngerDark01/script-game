"""Actual launcher import and Windows-spawn regressions, without game input."""
from __future__ import annotations

import ast
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "src/auto_modules/bootstrap/main.py"


def test_bootstrap_import_does_not_execute_gui_initialization():
    # Execute the real module with startup routines instrumented. This fails
    # before an old bootstrap can open logs, request UAC or acquire a mutex.
    tree = ast.parse(BOOTSTRAP.read_text(encoding="utf-8"))
    startup_functions = {
        "configure_runtime_output", "hide_console_if_not_debugging",
        "set_process_dpi_awareness", "is_running_as_admin", "relaunch_as_admin",
        "acquire_single_instance_lock", "has_existing_main_window",
    }
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in startup_functions:
            node.body = ast.parse(f"raise AssertionError('import side effect: {node.name}')").body
    namespace = {"__name__": "bootstrap_import_probe", "__file__": str(BOOTSTRAP)}
    before_streams = sys.stdout, sys.stderr
    exec(compile(ast.fix_missing_locations(tree), str(BOOTSTRAP), "exec"), namespace)
    assert (sys.stdout, sys.stderr) == before_streams
    assert callable(namespace["main"])
    assert namespace["_RUNTIME_LOG_HANDLE"] is None
    assert namespace["_SINGLE_INSTANCE_MUTEX_HANDLE"] is None
    assert "MainWindow" not in namespace and "QApplication" not in namespace


def _load_bootstrap():
    spec = importlib.util.spec_from_file_location("bootstrap_test", BOOTSTRAP)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_gui_initialization_order_and_exit_code(monkeypatch):
    from types import SimpleNamespace
    bootstrap = _load_bootstrap()
    events = []
    monkeypatch.setattr(bootstrap.multiprocessing, "freeze_support", lambda: events.append("freeze"))
    monkeypatch.setattr(bootstrap, "configure_runtime_output", lambda: events.append("logging"))
    monkeypatch.setattr(bootstrap, "hide_console_if_not_debugging", lambda: events.append("console"))
    monkeypatch.setattr(bootstrap, "set_process_dpi_awareness", lambda: events.append("dpi") or "test-dpi")
    monkeypatch.setattr(bootstrap, "is_running_as_admin", lambda: True)
    monkeypatch.setattr(bootstrap, "acquire_single_instance_lock", lambda: events.append("mutex") or True)
    monkeypatch.setattr(bootstrap, "has_existing_main_window", lambda: events.append("window_check") or False)

    def application(_args):
        events.append("qt")
        return SimpleNamespace(exec=lambda: 17)

    def window():
        events.append("window")
        return SimpleNamespace(show=lambda: events.append("show"))

    monkeypatch.setitem(sys.modules, "PySide6.QtWidgets", SimpleNamespace(QApplication=application))
    monkeypatch.setitem(sys.modules, "auto_modules.ui.main_window", SimpleNamespace(MainWindow=window))
    assert bootstrap.main() == 17
    assert events == ["freeze", "logging", "console", "dpi", "mutex", "window_check", "qt", "window", "show"]


@pytest.mark.skipif(os.name != "nt", reason="UAC launch behavior")
@pytest.mark.parametrize("granted,exit_code", [(True, 0), (False, 1)])
def test_gui_uac_result_returns_before_mutex_or_qt(monkeypatch, granted, exit_code):
    bootstrap = _load_bootstrap()
    monkeypatch.setattr(bootstrap, "configure_runtime_output", lambda: None)
    monkeypatch.setattr(bootstrap, "hide_console_if_not_debugging", lambda: None)
    monkeypatch.setattr(bootstrap, "set_process_dpi_awareness", lambda: "test-dpi")
    monkeypatch.setattr(bootstrap, "is_running_as_admin", lambda: False)
    monkeypatch.setattr(bootstrap, "relaunch_as_admin", lambda: granted)
    monkeypatch.setattr(bootstrap, "acquire_single_instance_lock", lambda: pytest.fail("UAC handoff must exit first"))
    assert bootstrap.main() == exit_code


def test_duplicate_gui_start_preserves_previous_runtime_log(tmp_path, monkeypatch):
    bootstrap = _load_bootstrap()
    monkeypatch.setattr(bootstrap, "data_root", lambda: tmp_path)
    monkeypatch.setattr(bootstrap, "hide_console_if_not_debugging", lambda: None)
    monkeypatch.setattr(bootstrap, "set_process_dpi_awareness", lambda: "test-dpi")
    monkeypatch.setattr(bootstrap, "is_running_as_admin", lambda: True)
    monkeypatch.setattr(bootstrap, "acquire_single_instance_lock", lambda: False)
    log_path = tmp_path / "logs/runtime.log"
    log_path.parent.mkdir()
    log_path.write_text("existing primary session evidence\n", encoding="utf-8")
    before_stdout, before_stderr = sys.stdout, sys.stderr
    try:
        assert bootstrap.main() == 0
        bootstrap._RUNTIME_LOG_HANDLE.flush()
    finally:
        sys.stdout, sys.stderr = before_stdout, before_stderr
        if bootstrap._RUNTIME_LOG_HANDLE is not None:
            bootstrap._RUNTIME_LOG_HANDLE.close()
    assert log_path.read_text(encoding="utf-8-sig").startswith("existing primary session evidence\n")


@pytest.mark.skipif(os.name != "nt", reason="Windows spawn and named-mutex regression")
def test_actual_root_entry_spawns_large_payload_with_gui_mutex_held(tmp_path):
    # A fresh interpreter sets the same __main__.__file__ as the real GUI.
    # Spawn therefore reimports ROOT/main.py, rather than this pytest entry.
    # The child target is an importable offline diagnostic, not a GUI or Host.
    code = r'''
import ctypes, multiprocessing as mp, sys
from pathlib import Path
from ctypes import wintypes
from auto_modules.bootstrap import main as bootstrap
from tools.debug.spawn_import_exit_probe import receive

kernel = ctypes.WinDLL("kernel32", use_last_error=True)
kernel.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
kernel.CreateMutexW.restype = wintypes.HANDLE
kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
mutex = kernel.CreateMutexW(None, False, bootstrap._single_instance_mutex_name())
assert mutex
sys.modules["__main__"].__file__ = str(Path("main.py").resolve())
process = mp.get_context("spawn").Process(target=receive, args=(bytes(6 * 1024 * 1024),))
try:
    process.start()
    process.join(10)
    assert not process.is_alive(), "child failed to finish"
    assert process.exitcode == 0, process.exitcode
    print("actual_entry_spawn_ok", flush=True)
finally:
    if process.is_alive():
        process.terminate()
        process.join(2)
    kernel.CloseHandle(mutex)
'''
    env = dict(os.environ, AUTO_MODULES_DATA_DIR=str(tmp_path),
               PYTHONPATH=os.pathsep.join((str(ROOT / "src"), str(ROOT))))
    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env,
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "child_target_reached bytes=6291456" in result.stdout
    assert "actual_entry_spawn_ok" in result.stdout
    assert not (tmp_path / "logs/runtime.log").exists()


@pytest.mark.skipif(os.name != "nt", reason="Actual Windows GUI entry preparation")
@pytest.mark.parametrize("leader", ["p1", "p2"])
def test_actual_root_entry_runs_large_map_vision_control_and_follower_output(tmp_path, leader):
    env = dict(os.environ, AUTO_MODULES_DATA_DIR=str(tmp_path),
               AUTO_MODULES_POE2_TERRAIN_LOG=str(tmp_path / "terrain.log"))
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools/debug/follow_root_entry_probe.py"), "--leader", leader],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=25,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"root_composition_ok leader={leader}" in result.stdout
    assert not (tmp_path / "logs/runtime.log").exists()
