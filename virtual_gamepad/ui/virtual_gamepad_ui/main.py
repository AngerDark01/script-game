from __future__ import annotations

import argparse
import ctypes
import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
CLIENT_ROOT = PACKAGE_ROOT / "client" / "python"
if str(CLIENT_ROOT) not in sys.path:
    sys.path.insert(0, str(CLIENT_ROOT))

from virtual_gamepad_client import JsonFileTransport, VirtualGamepadClient  # noqa: E402

from .main_window import MainWindow  # noqa: E402


def requires_elevation(*, is_windows: bool, is_admin: bool, demo: bool) -> bool:
    """The UI must match the host's integrity level to use its local pipe."""
    return is_windows and not is_admin and not demo


def is_administrator() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def restart_as_administrator(arguments: list[str]) -> bool:
    """Restart this exact module through UAC, preserving its command arguments."""
    params = subprocess.list2cmdline(["-m", "virtual_gamepad_ui.main", *arguments])
    result = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        sys.executable,
        params,
        str(PACKAGE_ROOT),
        1,
    )
    return int(result) > 32


class DemoClient:
    def __init__(self) -> None:
        self.running = True
        self.tick = 0
        self.requests: list[tuple[str, dict]] = []

    def status(self) -> dict:
        return {"runState": "Running" if self.running else "Paused", "driverInstalled": True, "deviceConnected": True, "message": "Demo mode"}

    def state(self, controller: int = 1) -> dict:
        self.tick += 1
        phase = self.tick % 80
        value = int((phase - 40) * 800)
        return {"buttons": 0x1000 if phase < 12 else 0, "leftTrigger": max(0, min(255, phase * 4)), "rightTrigger": 0, "leftStickX": value, "leftStickY": 20000 if phase < 40 else -20000, "rightStickX": -value, "rightStickY": 0}

    def start(self, controller: int = 1, *, source: str | None = None, sequence: int | None = None) -> None:
        self.running = True

    def pause(self, controller: int = 1, *, source: str | None = None, sequence: int | None = None) -> None:
        self.running = False

    def reset(self, controller: int = 1, *, source: str | None = None, sequence: int | None = None) -> None:
        self.running = False

    def emergency_reset(self) -> None:
        self.running = False

    def request(self, *_args, **_kwargs) -> dict:
        if _args:
            self.requests.append((_args[0], _kwargs.get("payload", {})))
        return {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true", help="Run with simulated input and no host process")
    args = parser.parse_args()
    if requires_elevation(is_windows=os.name == "nt", is_admin=is_administrator(), demo=args.demo):
        if restart_as_administrator(sys.argv[1:]):
            return 0
        print("Administrator permission is required for the virtual gamepad UI. It was not started.", file=sys.stderr)
        return 1
    app = QApplication(sys.argv)
    client_factory = DemoClient if args.demo else VirtualGamepadClient
    client = client_factory()
    window = MainWindow(
        client,
        demo=args.demo,
        profile_path=PACKAGE_ROOT / "configs" / "controller-1.json",
        client_factory=client_factory,
    )
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
