"""Short, foreground-gated PoE2 controller movement diagnostic.

Run elevated. This probe never sends LAN or keyboard input. It measures a
read-only player position before and after a bounded left-stick hold.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import sys
import time
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from auto_modules.adapters.virtual_gamepad import ProgramGamepadOutput, VirtualGamepadClient
from auto_modules.features.poe2.live_terrain.player_position import (
    Poe2PlayerPositionSource,
    find_process_id,
)

LOG = ROOT / "data" / "logs" / "poe2_movement_probe.jsonl"


def foreground_pid() -> int:
    """Return the PID owning the Windows foreground window."""
    ctypes.windll.user32.GetForegroundWindow.restype = ctypes.c_void_p
    ctypes.windll.user32.GetWindowThreadProcessId.argtypes = (ctypes.c_void_p, ctypes.c_void_p)
    handle = ctypes.windll.user32.GetForegroundWindow()
    pid = ctypes.c_ulong()
    ctypes.windll.user32.GetWindowThreadProcessId(handle, ctypes.byref(pid))
    return int(pid.value)


def record(step: str, **details: object) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"time": time.time(), "step": step, **details}, ensure_ascii=False) + "\n")


def run_bounded_output(
    output: ProgramGamepadOutput,
    *,
    game_pid: int,
    duration: float,
    current_foreground: Callable[[], int] = foreground_pid,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[str, int]:
    """Hold left stick briefly, neutralize and release even if focus changes."""
    if current_foreground() != game_pid:
        return "game_not_foreground", 0
    output.start()
    ticks = 0
    try:
        end = clock() + duration
        while clock() < end:
            if current_foreground() != game_pid:
                return "focus_lost", ticks
            output.write((1.0, 0.0), elapsed_ms=50, valid_for_ms=120)
            ticks += 1
            sleep(0.05)
        return "completed", ticks
    finally:
        try:
            output.write((0.0, 0.0), elapsed_ms=50, valid_for_ms=120)
        finally:
            output.stop()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--controller", type=int, choices=(1, 2), default=1)
    parser.add_argument("--duration", type=float, default=1.5)
    parser.add_argument("--settle-seconds", type=float, default=10.0)
    parser.add_argument("--wait-foreground", type=float, default=20.0)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    if (
        not 0 < args.duration <= 2.0
        or not 0 <= args.settle_seconds <= 30.0
        or not 0 <= args.wait_foreground <= 30.0
    ):
        parser.error("duration must be (0, 2] seconds; waits must be [0, 30] seconds")
    if not ctypes.windll.shell32.IsUserAnAdmin():
        record("blocked.not_elevated")
        return 2
    client = VirtualGamepadClient()
    output = ProgramGamepadOutput(client, controller=args.controller)
    try:
        game_pid = find_process_id()
        client.connect(timeout=3.0)
        record("connected", game_pid=game_pid, controller=args.controller, status=client.status())
        if args.check_only:
            before = Poe2PlayerPositionSource().read_once()
            record("position.before", grid=before.grid, instance=before.area_instance)
            return 0
        record("settle.start", seconds=args.settle_seconds)
        time.sleep(args.settle_seconds)
        record("settle.finished")
        deadline = time.monotonic() + args.wait_foreground
        while foreground_pid() != game_pid and time.monotonic() < deadline:
            time.sleep(0.1)
        if foreground_pid() != game_pid:
            record("blocked.game_not_foreground", game_pid=game_pid, foreground_pid=foreground_pid())
            return 3
        before = Poe2PlayerPositionSource().read_once()
        record("position.before", grid=before.grid, instance=before.area_instance)
        reason, ticks = run_bounded_output(output, game_pid=game_pid, duration=args.duration)
        record("output.finished", reason=reason, ticks=ticks, controller=args.controller)
        if ticks == 0:
            return 3
        after = Poe2PlayerPositionSource().read_once(before.area_instance)
        displacement = ((after.grid[0] - before.grid[0]) ** 2 + (after.grid[1] - before.grid[1]) ** 2) ** 0.5
        record("position.after", grid=after.grid, delta_grid=displacement, instance=after.area_instance)
        return 0 if reason == "completed" else 3
    except Exception as exc:
        record("failed", type=type(exc).__name__, error=str(exc))
        return 1
    finally:
        try:
            output.close()
        except Exception as exc:
            record("cleanup.failed", type=type(exc).__name__, error=str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
