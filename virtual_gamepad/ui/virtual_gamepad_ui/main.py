from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
CLIENT_ROOT = PACKAGE_ROOT / "client" / "python"
if str(CLIENT_ROOT) not in sys.path:
    sys.path.insert(0, str(CLIENT_ROOT))

from virtual_gamepad_client import JsonFileTransport, VirtualGamepadClient  # noqa: E402

from .main_window import MainWindow  # noqa: E402


class DemoClient:
    def __init__(self) -> None:
        self.running = True
        self.tick = 0

    def status(self) -> dict:
        return {"runState": "Running" if self.running else "Paused", "driverInstalled": True, "deviceConnected": True, "message": "Demo mode"}

    def state(self) -> dict:
        self.tick += 1
        phase = self.tick % 80
        value = int((phase - 40) * 800)
        return {"buttons": 0x1000 if phase < 12 else 0, "leftTrigger": max(0, min(255, phase * 4)), "rightTrigger": 0, "leftStickX": value, "leftStickY": 20000 if phase < 40 else -20000, "rightStickX": -value, "rightStickY": 0}

    def start(self) -> None:
        self.running = True

    def pause(self) -> None:
        self.running = False

    def emergency_reset(self) -> None:
        self.running = False

    def request(self, *_args, **_kwargs) -> dict:
        return {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true", help="Run with simulated input and no host process")
    args = parser.parse_args()
    app = QApplication(sys.argv)
    client = DemoClient() if args.demo else VirtualGamepadClient()
    window = MainWindow(client, demo=args.demo, profile_path=PACKAGE_ROOT / "configs" / "default.json")
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
