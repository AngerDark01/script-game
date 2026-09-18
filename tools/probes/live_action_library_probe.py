"""Exercise the real ``core.actions`` Virtual Xbox path and leave it neutral.

The independent Virtual Gamepad host must already be running.  This tool
elevates itself when needed because the host intentionally accepts clients at
the same Windows integrity level.  It starts only the selected controller,
sends one stick vector, one trigger value, and an A press through
``connect_action_adapter()``, verifies the host's live state,
then resets and pauses that controller in every exit path.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESULT_PATH = PROJECT_ROOT / "data" / "logs" / "live_action_library_probe.json"
for import_root in (PROJECT_ROOT / "src",):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from auto_modules.core.actions import (
    ActionCommand,
    ActionKind,
    GamepadButtonTarget,
    GamepadResetTarget,
    GamepadStickTarget,
    GamepadTriggerTarget,
    VirtualControllerRoute,
)
from auto_modules.adapters.virtual_gamepad import connect_action_adapter
def _is_administrator() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _restart_as_administrator(arguments: list[str]) -> bool:
    parameters = subprocess.list2cmdline([str(Path(__file__).resolve()), *arguments])
    result = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        sys.executable,
        parameters,
        str(PROJECT_ROOT),
        1,
    )
    return int(result) > 32


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--controller", choices=(1, 2), type=int, default=1)
    return parser.parse_args()


def _write_result(result: dict[str, Any]) -> None:
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def _checkpoint(result: dict[str, Any], phase: str) -> None:
    """Persist the current real-pipe phase so a blocked elevated probe is visible."""
    result["phase"] = phase
    _write_result(result)


def _live_state_is_expected(state: dict[str, Any]) -> bool:
    return (
        int(state.get("buttons", 0)) & 0x1000 != 0
        and int(state.get("leftStickX", 0)) == -12000
        and int(state.get("leftStickY", 0)) == 22000
        and int(state.get("rightTrigger", 0)) == 96
    )


def _state_is_neutral(state: dict[str, Any]) -> bool:
    return all(int(value) == 0 for value in state.values())


def run(controller: int) -> dict[str, Any]:
    result: dict[str, Any] = {"controller": controller, "success": False}
    adapter: VirtualGamepadActionAdapter | None = None
    host: Any | None = None
    route = VirtualControllerRoute(
        controller=controller,
        source="auto_modules.live_action_probe",
        ttl_ms=1200,
    )

    try:
        # This is the real library composition path, not a fake transport.
        _checkpoint(result, "connect_action_adapter")
        adapter = connect_action_adapter()
        # The probe asks this real client for observable host state. Production
        # workflows should stay on the public ActionAdapter boundary instead.
        host = adapter._device
        _checkpoint(result, "read_host_status")
        status = host.status()
        result["hostBefore"] = status
        if not status.get("driverInstalled") or not status.get("deviceConnected"):
            raise RuntimeError(f"Virtual Xbox is unavailable: {status}")

        _checkpoint(result, "start_controller")
        host.start(controller)
        _checkpoint(result, "submit_actions")
        adapter.execute(
            ActionCommand(
                ActionKind.GAMEPAD_STICK,
                GamepadStickTarget(route=route, stick="left", x=-12000, y=22000),
            )
        )
        adapter.execute(
            ActionCommand(
                ActionKind.GAMEPAD_TRIGGER,
                GamepadTriggerTarget(route=route, trigger="rt", value=96),
            )
        )
        adapter.execute(
            ActionCommand(
                ActionKind.GAMEPAD_BUTTON,
                GamepadButtonTarget(route=route, button="A", pressed=True),
            )
        )
        time.sleep(0.2)

        _checkpoint(result, "read_live_state")
        live_state = host.state(controller)
        result["liveState"] = live_state
        if not _live_state_is_expected(live_state):
            raise RuntimeError(f"Host state did not match submitted Xbox actions: {live_state}")

        adapter.execute(
            ActionCommand(ActionKind.GAMEPAD_RESET, GamepadResetTarget(route=route))
        )
        time.sleep(0.1)
        _checkpoint(result, "read_reset_state")
        result["stateAfterReset"] = host.state(controller)
        if not _state_is_neutral(result["stateAfterReset"]):
            raise RuntimeError(f"Controller did not return to neutral: {result['stateAfterReset']}")
        result["success"] = True
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        cleanup: dict[str, Any] = {"reset": False, "paused": False}
        if adapter is not None:
            try:
                adapter.execute(
                    ActionCommand(ActionKind.GAMEPAD_RESET, GamepadResetTarget(route=route))
                )
                cleanup["reset"] = True
            except Exception as exc:
                cleanup["resetError"] = f"{type(exc).__name__}: {exc}"
        if host is not None:
            try:
                host.pause(controller)
                cleanup["paused"] = True
            except Exception as exc:
                cleanup["pauseError"] = f"{type(exc).__name__}: {exc}"
        if adapter is not None:
            adapter.close()
        result["cleanup"] = cleanup

    return result


def main() -> int:
    args = _arguments()
    if os.name == "nt" and not _is_administrator():
        if _restart_as_administrator(sys.argv[1:]):
            print("Administrator restart requested; the elevated probe will write its result file.")
            return 0
        print("Administrator permission is required; the probe was not started.", file=sys.stderr)
        return 1

    result = run(args.controller)
    _write_result(result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
