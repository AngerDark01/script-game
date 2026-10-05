"""Bounded PoE2 route-input experiment for a pre-validated map target."""
from __future__ import annotations

import argparse
import ctypes
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from auto_modules.adapters.virtual_gamepad import ProgramGamepadOutput, VirtualGamepadClient
from auto_modules.adapters.windows import is_process_foreground
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_follow import (
    ControlMode,
    MapIdentity,
    PositionSample,
    RoleId,
    SimulatedFollowRuntime,
)
from auto_modules.features.poe2.live_terrain import (
    POE2_MAP_TO_STICK_BASIS,
    native_route_vector_for_program_output,
)
from auto_modules.features.poe2.live_terrain.player_position import (
    Poe2PlayerPositionSource,
    find_process_id,
)
import windows_capture as _windows_capture

MAP = ROOT / "data" / "poe2_live_terrain_test" / "latest.npz"
META = ROOT / "data" / "poe2_live_terrain_test" / "latest.json"
LOG = ROOT / "data" / "logs" / "poe2_route_probe.jsonl"


class _ProcessApi:
    """Use the current executable name while preserving the shared reader."""

    ProcessReader = _windows_capture.ProcessReader
    resolve_poe2_descriptor = staticmethod(_windows_capture.resolve_poe2_descriptor)
    resolve_poe2_layout = staticmethod(_windows_capture.resolve_poe2_layout)

    @staticmethod
    def find_process_id() -> int:
        return _windows_capture.find_process_id(
            ("PathOfExile.exe", "PathOfExileSteam.exe", "PathOfExile")
        )


def record(step: str, **details: object) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"time": time.time(), "step": step, **details}) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-x", type=float, default=630.0)
    parser.add_argument("--target-y", type=float, default=925.0)
    parser.add_argument("--controller", type=int, choices=(1, 2), default=1)
    parser.add_argument("--settle-seconds", type=float, default=10.0)
    parser.add_argument("--speed", type=float, default=35.0)
    parser.add_argument("--max-seconds", type=float, default=15.0)
    parser.add_argument("--registration-angle", type=float, default=0.0)
    parser.add_argument("--registration-scale", type=float, default=1.0)
    parser.add_argument("--registration-reflect-horizontal", action="store_true")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="只使用 latest.npz 和显式起点做路线回放，不读取进程、不发送手柄输入",
    )
    parser.add_argument("--start-x", type=float, default=None)
    parser.add_argument("--start-y", type=float, default=None)
    args = parser.parse_args()
    if (
        not 0 < args.settle_seconds <= 30
        or not 0 < args.speed <= 100
        or not 0 < args.max_seconds <= 30
        or not math.isfinite(args.registration_scale)
        or args.registration_scale <= 0
    ):
        parser.error("invalid bounds")
    metadata = json.loads(META.read_text(encoding="utf-8"))
    identity = MapIdentity(str(metadata["area_id"]), str(metadata["instance_id"]))
    wall_map = np.load(MAP, allow_pickle=False)["wall_layer"]
    if args.offline:
        if args.start_x is None or args.start_y is None:
            parser.error("--offline requires --start-x and --start-y")
        start = (float(args.start_x), float(args.start_y))
        target = (args.target_x, args.target_y)
        runtime = SimulatedFollowRuntime(
            wall_map=wall_map,
            map_identity=identity,
            arrival_radius=8.0,
            speed_units_per_second=args.speed,
            position_ttl_ms=2000,
            downsample_factor=8,
            safety_margin=0,
            clearance_radius=20.0,
            clearance_weight=2.0,
            dead_end_weight=0.75,
            minimum_clearance=0.0,
            footprint_radius=0.0,
            inflate_collision=False,
        )
        # Exercise the same runtime boundary contract as the page.  Calling
        # _plan_safe_route() directly would reject a continuous native point
        # that rounds onto a wall cell even when the adjacent cell is open.
        role = RoleId("offline-probe", "p1")
        runtime.add_follower(
            role,
            PositionSample(
                role=role,
                map_identity=identity,
                position=start,
                captured_at_ms=100,
                confidence=1.0,
                source="offline",
            ),
            mode=ControlMode.PREVIEW,
        )
        runtime.set_simulated_target(target, now_ms=100)
        observation = runtime.tick(now_ms=100)[role.key]
        route = observation.route or None
        diagnostics = dict(observation.diagnostics)
        diagnostics["reason"] = observation.reason
        diagnostics["vector"] = observation.vector
        details = {
            "map_instance": identity.map_version,
            "start": start,
            "target": target,
            "route": route,
            "route_available": bool(route),
            "diagnostics": diagnostics,
            "mode": "offline",
        }
        record("offline.route", **details)
        print(json.dumps(details, ensure_ascii=False, default=str))
        return 0 if route else 4
    if not ctypes.windll.shell32.IsUserAnAdmin():
        record("blocked.not_elevated")
        return 2
    client = None
    output = None
    try:
        source = Poe2PlayerPositionSource(api=_ProcessApi())
        pid = int(_ProcessApi.find_process_id())
        before = source.read_once(identity.map_version)
        runtime = SimulatedFollowRuntime(
            wall_map=wall_map, map_identity=identity,
            arrival_radius=8.0, speed_units_per_second=args.speed,
            position_ttl_ms=2000, downsample_factor=8,
            safety_margin=0, clearance_radius=20.0, clearance_weight=2.0,
            dead_end_weight=0.75, minimum_clearance=0.0, footprint_radius=0.0,
            inflate_collision=False,
        )
        target = (args.target_x, args.target_y)
        route = runtime._plan_safe_route(before.grid, target)
        if not route:
            record("blocked.no_safe_route", start=before.grid, target=target)
            return 4
        points = [before.grid, *route, target]
        length = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(points, points[1:]))
        record("route.ready", pid=pid, map_instance=before.area_instance,
               start=before.grid, target=target, nodes=len(route), length=length,
               registration_angle=args.registration_angle,
               registration_scale=args.registration_scale,
               registration_reflect_horizontal=args.registration_reflect_horizontal)
        record("settle.start", seconds=args.settle_seconds)
        time.sleep(args.settle_seconds)
        if not is_process_foreground(pid):
            record("blocked.game_not_foreground", pid=pid)
            return 3
        client = VirtualGamepadClient()
        output = ProgramGamepadOutput(
            client,
            controller=args.controller,
            basis=POE2_MAP_TO_STICK_BASIS,
        )
        client.connect(timeout=3.0)
        output.start()
        started = time.monotonic()
        ticks = 0
        reason = "completed"
        code = 0
        try:
            for first, second in zip(points, points[1:]):
                dx, dy = second[0] - first[0], second[1] - first[1]
                distance = math.hypot(dx, dy)
                if distance < 1e-6:
                    continue
                vector = native_route_vector_for_program_output(
                    (dx / distance, dy / distance)
                )
                end = time.monotonic() + min(2.0, distance / args.speed)
                while time.monotonic() < end:
                    if not is_process_foreground(pid):
                        reason, code = "focus_lost", 3
                        break
                    if time.monotonic() - started > args.max_seconds:
                        reason, code = "timeout", 3
                        break
                    output.write(vector, elapsed_ms=50, valid_for_ms=120)
                    ticks += 1
                    time.sleep(0.05)
                if code:
                    break
        finally:
            try:
                output.write((0.0, 0.0), elapsed_ms=50, valid_for_ms=120)
            finally:
                output.stop()
                client.close()
        after = source.read_once(identity.map_version)
        delta = math.hypot(after.grid[0] - before.grid[0], after.grid[1] - before.grid[1])
        record("route.finished", reason=reason, ticks=ticks,
               before=before.grid, after=after.grid, delta_grid=delta,
               instance=after.area_instance)
        return code
    except Exception as exc:
        record("failed", type=type(exc).__name__, error=str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
