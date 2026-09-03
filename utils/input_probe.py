"""
Standalone input probe for testing which mouse strategy is accepted by the game.

Default mode is diagnostic only. Add --execute to send real mouse input.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import sys
import time
from pathlib import Path


def set_process_dpi_awareness():
    """Match the older working script: use physical screen coordinates."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return "shcore.SetProcessDpiAwareness(2)"
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
            return "user32.SetProcessDPIAware()"
        except Exception as exc:
            return f"failed: {type(exc).__name__}: {exc}"


DPI_AWARENESS_RESULT = set_process_dpi_awareness()

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pydirectinput

from core.input import InputDriver


MODES = (
    "t2_click",
    "pydi_click_xy",
    "pydi_move_click",
    "pydi_hold_xy",
    "setcursor_pydi_click",
    "setcursor_pydi_hold",
    "setcursor_win32_click",
)


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def restart_as_admin():
    args = [arg for arg in sys.argv if arg != "--restart-admin"]
    params = " ".join(f'"{arg}"' for arg in args)
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)


def normalize_button(button: str) -> str:
    if button in {"primary", "left"}:
        return "left"
    if button in {"secondary", "right"}:
        return "right"
    return button


def format_window(window_info):
    if not window_info:
        return None
    return {
        "hwnd": window_info.get("hwnd"),
        "pid": window_info.get("pid"),
        "class_name": window_info.get("class_name"),
        "title": window_info.get("title"),
    }


def collect_state(driver: InputDriver, x: int, y: int):
    foreground = driver.foreground_window()
    foreground_info = driver.describe_window(foreground) if foreground else None
    return {
        "target": [int(x), int(y)],
        "dpi_awareness": DPI_AWARENESS_RESULT,
        "is_admin": is_admin(),
        "pydirectinput_size": list(pydirectinput.size()),
        "pydirectinput_position": list(pydirectinput.position()),
        "win32_cursor": list(driver.cursor_pos() or (None, None)),
        "clip_cursor": driver.clip_cursor_rect(),
        "target_window": format_window(driver.describe_window_at(x, y)),
        "foreground_window": format_window(foreground_info),
    }


def print_state(label: str, driver: InputDriver, x: int, y: int):
    print(f"\n=== {label} ===")
    print(json.dumps(collect_state(driver, x, y), ensure_ascii=False, indent=2))


def countdown(seconds: float):
    seconds = max(0.0, float(seconds))
    if seconds <= 0:
        return
    print(f"Executing in {seconds:.1f}s. Keep the game state ready...")
    end_time = time.time() + seconds
    while True:
        remaining = end_time - time.time()
        if remaining <= 0:
            break
        print(f"  {remaining:.1f}s")
        time.sleep(min(1.0, remaining))


def execute_mode(mode: str, driver: InputDriver, x: int, y: int, args):
    pydi_button = args.button
    win_button = normalize_button(args.button)
    delay = max(0.0, float(args.delay))
    hold = max(0.0, float(args.hold))

    print(f"\n--- mode={mode} target=({x}, {y}) ---")
    before = collect_state(driver, x, y)
    print("before:", json.dumps(before, ensure_ascii=False))

    if args.focus_target:
        focused = driver.focus_window_at(x, y)
        time.sleep(max(0.0, float(args.focus_delay)))
        print("after_focus:", json.dumps(collect_state(driver, x, y), ensure_ascii=False), "focused=", focused)

    if mode == "pydi_click_xy":
        pydirectinput.click(x, y, button=pydi_button)

    elif mode == "t2_click":
        ctypes.windll.user32.SetCursorPos(int(x), int(y))
        time.sleep(0.05)
        ctypes.windll.user32.mouse_event(2, 0, 0, 0, 0)
        time.sleep(0.05)
        ctypes.windll.user32.mouse_event(4, 0, 0, 0, 0)

    elif mode == "pydi_move_click":
        pydirectinput.moveTo(x, y)
        time.sleep(delay)
        print("after_move:", json.dumps(collect_state(driver, x, y), ensure_ascii=False))
        pydirectinput.click(button=pydi_button)

    elif mode == "pydi_hold_xy":
        pydirectinput.moveTo(x, y)
        time.sleep(delay)
        print("after_move:", json.dumps(collect_state(driver, x, y), ensure_ascii=False))
        pydirectinput.mouseDown(button=pydi_button)
        time.sleep(hold)
        pydirectinput.mouseUp(button=pydi_button)

    elif mode == "setcursor_pydi_click":
        moved = driver.move_to(x, y)
        time.sleep(delay)
        print("after_setcursor:", json.dumps(collect_state(driver, x, y), ensure_ascii=False), "moved=", moved)
        pydirectinput.click(button=pydi_button)

    elif mode == "setcursor_pydi_hold":
        moved = driver.move_to(x, y)
        time.sleep(delay)
        print("after_setcursor:", json.dumps(collect_state(driver, x, y), ensure_ascii=False), "moved=", moved)
        pydirectinput.mouseDown(button=pydi_button)
        time.sleep(hold)
        pydirectinput.mouseUp(button=pydi_button)

    elif mode == "setcursor_win32_click":
        driver.click(x, y, button=win_button, hold_seconds=hold, move_delay=delay)

    else:
        raise ValueError(f"Unknown mode: {mode}")

    time.sleep(max(0.05, float(args.after_delay)))
    after = collect_state(driver, x, y)
    print("after:", json.dumps(after, ensure_ascii=False))


def parse_args():
    parser = argparse.ArgumentParser(description="Probe game mouse input behavior.")
    parser.add_argument("--x", type=int, help="Target screen X. Defaults to current cursor X.")
    parser.add_argument("--y", type=int, help="Target screen Y. Defaults to current cursor Y.")
    parser.add_argument("--mode", choices=MODES, default="pydi_click_xy")
    parser.add_argument("--all", action="store_true", help="Run all probe modes in sequence.")
    parser.add_argument("--execute", action="store_true", help="Actually send mouse input. Without this, only diagnostics are printed.")
    parser.add_argument("--countdown", type=float, default=3.0)
    parser.add_argument("--delay", type=float, default=0.08, help="Delay after moving before clicking.")
    parser.add_argument("--hold", type=float, default=0.12, help="Mouse hold duration for hold modes.")
    parser.add_argument("--after-delay", type=float, default=0.25, help="Delay before after-state diagnostics.")
    parser.add_argument("--button", default="primary", choices=("primary", "left", "secondary", "right"))
    parser.add_argument("--focus-target", action="store_true", help="Focus the window under the target point before sending input.")
    parser.add_argument("--focus-delay", type=float, default=0.3, help="Delay after focusing the target window.")
    parser.add_argument("--restart-admin", action="store_true", help="Restart this probe with UAC elevation, matching t2.py behavior.")
    parser.add_argument("--list-modes", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.list_modes:
        print("\n".join(MODES))
        return 0
    if args.restart_admin and not is_admin():
        restart_as_admin()
        return 0

    driver = InputDriver()
    use_live_cursor = args.x is None and args.y is None
    current = driver.cursor_pos() or pydirectinput.position()
    x = int(args.x if args.x is not None else current[0])
    y = int(args.y if args.y is not None else current[1])

    print_state("initial diagnostics", driver, x, y)
    if not args.execute:
        print("\nDry run only. Add --execute to send real mouse input.")
        return 0

    modes = MODES if args.all else (args.mode,)
    countdown(args.countdown)
    if use_live_cursor:
        current = driver.cursor_pos() or pydirectinput.position()
        x = int(current[0])
        y = int(current[1])
        print_state("target sampled after countdown", driver, x, y)
    for mode in modes:
        execute_mode(mode, driver, x, y, args)
        if args.all:
            print("\nObserve whether the game reacted, then prepare for next mode.")
            time.sleep(1.0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
