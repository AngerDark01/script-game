"""Start the independent virtual gamepad host and its UI at one integrity level.

Run this file (or the matching PowerShell command in the README) once.  It
requests Administrator permission once, starts the C# host in the background,
waits for its pipe, then starts the PySide6 UI.  The UI and host are both
elevated because the pipe intentionally requires the same user and integrity
level on Windows.
"""

from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Mapping


AUTO_MODULES_ROOT = Path(__file__).resolve().parents[2]
MODULE_ROOT = AUTO_MODULES_ROOT / "services" / "virtual_gamepad"
SOURCE_ROOT = AUTO_MODULES_ROOT / "src"
HOST_ROOT = MODULE_ROOT / "host" / "src" / "VirtualGamepadHost" / "bin" / "Release" / "net8.0-windows"
HOST_EXE = HOST_ROOT / "VirtualGamepadHost.exe"
HOST_DLL = HOST_ROOT / "VirtualGamepadHost.dll"
UI_ROOT = SOURCE_ROOT / "auto_modules" / "ui" / "virtual_gamepad"
CLIENT_ROOT = SOURCE_ROOT / "auto_modules" / "adapters" / "virtual_gamepad"
PIPE_PATH = r"\\.\pipe\AutoModules.VirtualGamepad.v1"
PATH_SEPARATOR = os.pathsep
DOTNET_CANDIDATES = (
    AUTO_MODULES_ROOT.parent / "dotnet-sdk2" / "dotnet.exe",
    Path(sys.executable).with_name("dotnet.exe"),
)

if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from auto_modules.adapters.virtual_gamepad import VirtualGamepadClient, VirtualGamepadError


def requires_elevation(*, is_windows: bool, is_admin: bool) -> bool:
    return is_windows and not is_admin


def is_administrator() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def restart_as_administrator(arguments: list[str]) -> bool:
    """Relaunch this exact launcher through UAC, preserving its arguments."""
    params = subprocess.list2cmdline([str(Path(__file__).resolve()), *arguments])
    result = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        sys.executable,
        params,
        str(MODULE_ROOT),
        1,
    )
    return int(result) > 32


def select_ui_python(python: Path) -> Path:
    """Prefer pythonw so the launcher leaves only the UI window visible."""
    pythonw = python.with_name("pythonw.exe")
    return pythonw if pythonw.exists() else python


def ui_environment(base: Mapping[str, str] | None = None) -> dict[str, str]:
    environment = dict(base or os.environ)
    roots = [str(SOURCE_ROOT)]
    existing = environment.get("PYTHONPATH", "")
    if existing:
        roots.append(existing)
    environment["PYTHONPATH"] = PATH_SEPARATOR.join(roots)
    return environment


def host_is_reachable() -> bool:
    """Check the user-local pipe without changing host state."""
    client = VirtualGamepadClient(pipe_path=PIPE_PATH)
    try:
        client.connect(timeout=0.1)
        return True
    except VirtualGamepadError:
        return False
    finally:
        client.close()


def host_command() -> list[str]:
    """Use the workspace runtime; the build apphost may be framework-dependent."""
    if HOST_DLL.exists():
        for candidate in DOTNET_CANDIDATES:
            if candidate.exists():
                return [str(candidate), "exec", str(HOST_DLL)]
        dotnet = shutil.which("dotnet")
        if dotnet:
            return [dotnet, "exec", str(HOST_DLL)]
    if HOST_EXE.exists():
        return [str(HOST_EXE)]
    raise FileNotFoundError(
        f"No .NET runtime was found and the compiled host is unavailable: {HOST_DLL}"
    )


def start_host() -> subprocess.Popen[bytes] | None:
    if host_is_reachable():
        return None
    if not HOST_DLL.exists() and not HOST_EXE.exists():
        raise FileNotFoundError(
            f"Compiled host was not found: {HOST_DLL}. Build the Release host before starting the UI."
        )

    creation_flags = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
    return subprocess.Popen(
        host_command(),
        cwd=str(HOST_ROOT),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creation_flags,
    )


def wait_for_host(timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + max(0.0, timeout)
    while time.monotonic() < deadline:
        if host_is_reachable():
            return True
        time.sleep(0.05)
    return host_is_reachable()


def start_ui() -> subprocess.Popen[bytes]:
    python = select_ui_python(Path(sys.executable))
    creation_flags = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
    return subprocess.Popen(
        [str(python), "-m", "auto_modules.ui.virtual_gamepad.main"],
        cwd=str(UI_ROOT),
        env=ui_environment(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creation_flags,
    )


def main() -> int:
    if requires_elevation(is_windows=os.name == "nt", is_admin=is_administrator()):
        if restart_as_administrator(sys.argv[1:]):
            return 0
        print("Administrator permission is required for the virtual gamepad. It was not started.", file=sys.stderr)
        return 1

    start_host()
    if not wait_for_host():
        print(f"The host did not create its pipe: {PIPE_PATH}", file=sys.stderr)
        return 1
    start_ui()
    print("Virtual Gamepad host and UI started. F7/F8 start or pause controller 1/2; F9 emergency-resets both.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
