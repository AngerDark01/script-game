"""Safely verify the real game-input -> virtual Xbox mapping path.

This is deliberately a short, one-shot diagnostic tool.  It brings only the
requested game window to the foreground, temporarily maps a keyboard key to
one Xbox button, and verifies that the Xbox state changes while the project
input layer holds that key.  Every exit path releases the key, restores the
previous mapping, and pauses the host.

Example (from ``D:\\ACloud\\auto_modules``)::

    D:\\ACloud\\.venv\\Scripts\\python.exe tools\\virtual_gamepad\\live_gamepad_probe.py
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


MODULE_ROOT = Path(__file__).resolve().parent
AUTOMODULES_ROOT = MODULE_ROOT.parents[1]
SOURCE_ROOT = AUTOMODULES_ROOT / "src"
for import_root in (SOURCE_ROOT,):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

import pydirectinput

from auto_modules.adapters.windows.window_finder import find_game_window
from auto_modules.adapters.input.win32_driver import InputDriver
from auto_modules.adapters.virtual_gamepad import VirtualGamepadClient


BUTTON_MASKS = {
    "dpadup": 0x0001,
    "dpaddown": 0x0002,
    "dpadleft": 0x0004,
    "dpadright": 0x0008,
    "start": 0x0010,
    "back": 0x0020,
    "leftthumb": 0x0040,
    "rightthumb": 0x0080,
    "leftshoulder": 0x0100,
    "rightshoulder": 0x0200,
    "a": 0x1000,
    "b": 0x2000,
    "x": 0x4000,
    "y": 0x8000,
}

INTEGRITY_RANKS = {
    0x1000: 1,  # low
    0x2000: 2,  # medium
    0x2100: 3,  # medium plus
    0x3000: 4,  # high / administrator
    0x4000: 5,  # system
    0x5000: 6,  # protected process
}
INTEGRITY_LABELS = {
    0x1000: "low",
    0x2000: "medium",
    0x2100: "medium_plus",
    0x3000: "high",
    0x4000: "system",
    0x5000: "protected",
}


class ProbeFailure(RuntimeError):
    """An expected condition for a failed live-input probe."""


def is_administrator() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def restart_as_administrator(arguments: list[str]) -> bool:
    """Restart this probe through UAC so it can inject into an elevated game."""
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-title", default="Path of Exile 2", help="Unique substring of the target game window title.")
    parser.add_argument("--key", default="J", help="Keyboard key to send through the project's DirectInput path.")
    parser.add_argument("--button", default="A", choices=sorted(name.upper() for name in BUTTON_MASKS), help="Temporary Xbox button target.")
    parser.add_argument("--controller", type=int, choices=(1, 2), default=1, help="Virtual controller slot to probe.")
    parser.add_argument("--hold-ms", type=int, default=180, help="How long to hold the keyboard input (50-1000 ms).")
    parser.add_argument(
        "--assume-focused",
        action="store_true",
        help="Skip the internal window-focus request when a caller has already activated the exact game window.",
    )
    return parser.parse_args()


def focus_game_window(title: str) -> dict[str, Any]:
    """Use the project's window/input helpers to focus exactly one game window."""
    window = find_game_window(title_substring=title, class_substring="")
    if window is None:
        raise ProbeFailure(f"No visible game window contains {title!r}.")

    driver = InputDriver()
    user32 = driver.user32
    hwnd = int(window.hwnd)
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE, only for a minimized game.
    focus_requested = bool(user32.SetForegroundWindow(hwnd))

    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        if int(user32.GetForegroundWindow() or 0) == hwnd:
            return {
                "focused": True,
                "focusRequested": focus_requested,
                "hwnd": hwnd,
                "pid": window.title and driver.describe_window(hwnd).get("pid"),
                "title": window.title,
            }
        time.sleep(0.05)

    foreground = driver.describe_window(int(user32.GetForegroundWindow() or 0))
    raise ProbeFailure(
        f"Game window was found but could not be focused. Current foreground window: {foreground}."
    )


def process_integrity(pid: int) -> dict[str, Any]:
    """Read a process integrity level without changing its privileges or state."""
    process_query_limited_information = 0x1000
    token_query = 0x0008
    token_integrity_level = 25
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_bool, ctypes.c_uint32]
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    advapi32.OpenProcessToken.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p)]
    advapi32.OpenProcessToken.restype = ctypes.c_bool
    advapi32.GetTokenInformation.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32),
    ]
    advapi32.GetTokenInformation.restype = ctypes.c_bool
    advapi32.GetSidSubAuthorityCount.argtypes = [ctypes.c_void_p]
    advapi32.GetSidSubAuthorityCount.restype = ctypes.POINTER(ctypes.c_byte)
    advapi32.GetSidSubAuthority.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    advapi32.GetSidSubAuthority.restype = ctypes.POINTER(ctypes.c_uint32)

    class SidAndAttributes(ctypes.Structure):
        _fields_ = [("sid", ctypes.c_void_p), ("attributes", ctypes.c_uint32)]

    class TokenMandatoryLabel(ctypes.Structure):
        _fields_ = [("label", SidAndAttributes)]

    process = kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not process:
        return {"pid": pid, "error": f"OpenProcess failed (winerror={ctypes.get_last_error()})"}
    token = ctypes.c_void_p()
    try:
        if not advapi32.OpenProcessToken(process, token_query, ctypes.byref(token)):
            return {"pid": pid, "error": f"OpenProcessToken failed (winerror={ctypes.get_last_error()})"}
        size = ctypes.c_uint32()
        advapi32.GetTokenInformation(token, token_integrity_level, None, 0, ctypes.byref(size))
        buffer = ctypes.create_string_buffer(size.value)
        if not advapi32.GetTokenInformation(token, token_integrity_level, buffer, size, ctypes.byref(size)):
            return {"pid": pid, "error": f"GetTokenInformation failed (winerror={ctypes.get_last_error()})"}
        label = ctypes.cast(buffer, ctypes.POINTER(TokenMandatoryLabel)).contents
        count = advapi32.GetSidSubAuthorityCount(label.label.sid).contents.value
        rid = advapi32.GetSidSubAuthority(label.label.sid, count - 1).contents.value
        return {"pid": pid, "rid": rid, "level": INTEGRITY_LABELS.get(rid, f"unknown_{rid:#x}")}
    finally:
        if token:
            kernel32.CloseHandle(token)
        kernel32.CloseHandle(process)


def sender_is_lower_integrity(sender: dict[str, Any], target: dict[str, Any]) -> bool:
    """Return true only when both processes expose known levels and sender is lower."""
    sender_rank = INTEGRITY_RANKS.get(sender.get("rid"))
    target_rank = INTEGRITY_RANKS.get(target.get("rid"))
    return sender_rank is not None and target_rank is not None and sender_rank < target_rank


def button_is_pressed(state: dict[str, Any], button: str) -> bool:
    return int(state.get("buttons", 0)) & BUTTON_MASKS[button.lower()] != 0


def neutral_state(state: dict[str, Any]) -> bool:
    return all(int(value) == 0 for value in state.values())


def run_probe(args: argparse.Namespace) -> dict[str, Any]:
    key = args.key.strip().upper()
    button = args.button.strip().upper()
    hold_seconds = max(0.05, min(args.hold_ms, 1000) / 1000.0)
    result: dict[str, Any] = {
        "gameTitle": args.game_title,
        "key": key,
        "button": button,
        "controller": args.controller,
        "holdMs": int(hold_seconds * 1000),
        "success": False,
    }
    client = VirtualGamepadClient()
    original_config: dict[str, Any] | None = None
    config_changed = False
    key_down = False

    try:
        client.connect()
        status = client.status()
        result["hostBefore"] = status
        if not status.get("driverInstalled") or not status.get("deviceConnected"):
            raise ProbeFailure(f"Virtual Xbox is unavailable: {status}")

        target_window = find_game_window(title_substring=args.game_title, class_substring="")
        if target_window is None:
            raise ProbeFailure(f"No visible game window contains {args.game_title!r}.")
        target_description = InputDriver().describe_window(target_window.hwnd)
        if target_description is None:
            raise ProbeFailure(f"Could not inspect the game window for {args.game_title!r}.")
        sender_integrity = process_integrity(os.getpid())
        target_integrity = process_integrity(int(target_description["pid"]))
        result["integrity"] = {"probe": sender_integrity, "game": target_integrity}
        if sender_is_lower_integrity(sender_integrity, target_integrity):
            raise ProbeFailure(
                f"The game runs at {target_integrity['level']} integrity but this probe runs at "
                f"{sender_integrity['level']}. Windows blocks the simulated key before it can reach "
                "the mapping host. Run the host and this probe from an Administrator terminal."
            )

        # Establish the safe starting state before this process can suppress an input.
        client.emergency_reset()
        original_config = client.request("get_config", {"controller": args.controller})
        temporary_config = {
            "controller": args.controller,
            "bindings": [{"source": f"keyboard:{key}", "target": f"button:{button}"}],
            "startPause": original_config.get("startPause", "F7"),
            "emergencyReset": original_config.get("emergencyReset", "F9"),
        }
        client.request("set_config", temporary_config)
        config_changed = True
        result["gameWindow"] = (
            {"focused": True, "focusRequested": False, "title": args.game_title, "focusSource": "caller"}
            if args.assume_focused
            else focus_game_window(args.game_title)
        )

        # pydirectinput is the same DirectInput sender used by MotionController.
        # Holding it lets us inspect the virtual Xbox state while the input is live.
        client.start(args.controller)
        pydirectinput.keyDown(key.lower())
        key_down = True
        time.sleep(hold_seconds)
        held_state = client.state(args.controller)
        result["heldState"] = held_state
        if not button_is_pressed(held_state, button):
            raise ProbeFailure(
                f"{key} was sent while mapping was active, but Xbox {button} was not pressed: {held_state}"
            )

        pydirectinput.keyUp(key.lower())
        key_down = False
        time.sleep(0.12)
        released_state = client.state(args.controller)
        result["releasedState"] = released_state
        if not neutral_state(released_state):
            raise ProbeFailure(f"Xbox state did not return to neutral after releasing {key}: {released_state}")

        result["success"] = True
        result["finding"] = (
            "The real project DirectInput path reached the host and produced the requested Xbox state. "
            "If the focused game did not react, investigate game-side XInput settings or process permissions."
        )
    except (ProbeFailure, OSError, RuntimeError) as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["note"] = "The probe could not establish the requested mapping state; cleanup is still running."
    finally:
        cleanup: dict[str, Any] = {"keyReleased": False, "mapping": "unchanged", "hostPaused": False}
        try:
            if key_down:
                pydirectinput.keyUp(key.lower())
            cleanup["keyReleased"] = True
        except Exception as exc:  # Keep cleanup going even if DirectInput itself failed.
            cleanup["keyReleaseError"] = f"{type(exc).__name__}: {exc}"
        try:
            if config_changed and original_config is not None:
                original_config["controller"] = args.controller
                client.request("set_config", original_config)
                cleanup["mapping"] = "restored"
        except Exception as exc:
            cleanup["mappingRestoreError"] = f"{type(exc).__name__}: {exc}"
        try:
            client.emergency_reset()
            status_after = client.status()
            controllers = status_after.get("controllers", [])
            cleanup["hostPaused"] = all(str(item.get("runState", "")).lower() in {"paused", "ready"} for item in controllers) if controllers else str(status_after.get("runState", "")).lower() == "paused"
        except Exception as exc:
            cleanup["hostPauseError"] = f"{type(exc).__name__}: {exc}"
        finally:
            client.close()
        result["cleanup"] = cleanup

    return result


def main() -> int:
    args = parse_args()
    if os.name == "nt" and not is_administrator():
        if restart_as_administrator(sys.argv[1:]):
            print("Administrator restart requested; the elevated probe will continue separately.")
            return 0
        print("Administrator permission is required for the live game probe. It was not started.", file=sys.stderr)
        return 1
    try:
        result = run_probe(args)
    except Exception as exc:
        result = {
            "success": False,
            "error": f"{type(exc).__name__}: {exc}",
            "note": "Cleanup was attempted: the keyboard key is released and the mapping host is paused.",
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
