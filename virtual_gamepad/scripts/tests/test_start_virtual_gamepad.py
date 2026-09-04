import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "start_virtual_gamepad.py"
SPEC = importlib.util.spec_from_file_location("start_virtual_gamepad", SCRIPT)
launcher = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(launcher)


def test_launcher_elevates_only_when_needed():
    assert launcher.requires_elevation(is_windows=True, is_admin=False)
    assert not launcher.requires_elevation(is_windows=True, is_admin=True)
    assert not launcher.requires_elevation(is_windows=False, is_admin=False)


def test_ui_command_uses_pythonw_when_available(tmp_path: Path):
    python = tmp_path / "python.exe"
    pythonw = tmp_path / "pythonw.exe"
    python.touch()
    pythonw.touch()

    assert launcher.select_ui_python(python) == pythonw


def test_ui_environment_contains_both_module_roots():
    environment = launcher.ui_environment({"PYTHONPATH": "existing"})
    entries = environment["PYTHONPATH"].split(launcher.PATH_SEPARATOR)

    assert str(launcher.UI_ROOT) in entries
    assert str(launcher.CLIENT_ROOT) in entries
    assert str(launcher.AUTO_MODULES_ROOT) in entries


def test_host_command_uses_workspace_dotnet_runtime_when_available(tmp_path: Path, monkeypatch):
    dotnet = tmp_path / "dotnet.exe"
    dotnet.touch()
    monkeypatch.setattr(launcher, "DOTNET_CANDIDATES", (dotnet,))

    command = launcher.host_command()

    assert command == [str(dotnet), "exec", str(launcher.HOST_DLL)]
