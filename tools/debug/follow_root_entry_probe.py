"""Offline real-entry spawn check with a large map and recording-only output.

Invoked by a timeout-bounded subprocess test. No game capture, memory source,
Host or physical input is used. The child preparation imports actual main.py.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from pathlib import Path
import sys
import time
from types import SimpleNamespace


class OfflineCaptureBackend:
    def capture(self, _left, _top, width, height):
        import cv2
        import numpy as np
        image = np.zeros((height, width, 3), dtype=np.uint8)
        cv2.rectangle(image, (8, 8), (108, 108), (255, 255, 255), 2)
        cv2.circle(image, (30, 40), 3, (0, 0, 255), -1)
        cv2.circle(image, (82, 72), 3, (0, 255, 255), -1)
        return image

    def close(self):
        pass


class RecordingOutput:
    def __init__(self, controller):
        self.controller = controller
        self.writes = []

    def start(self):
        pass

    def write(self, vector, *, elapsed_ms):
        self.writes.append((tuple(vector), elapsed_ms))

    def heartbeat(self):
        return True

    def rearm(self):
        pass

    def stop(self):
        pass

    def close(self):
        pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--leader", choices=("p1", "p2"), default="p1")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / "src"))
    sys.path.insert(0, str(root))
    import numpy as np
    from auto_modules.bootstrap import main as bootstrap
    from auto_modules.core.spatial.monitor_binding import CaptureRect, MonitorBinding
    from auto_modules.features.poe2.live_terrain.experimental.follow_engine.composition import FollowSeedBundle
    from auto_modules.features.poe2.live_terrain.experimental.follow_engine.engine import FollowEngineStart
    from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import SimilarityTransform2D
    from auto_modules.ui.modes.poe2_live_terrain.follow_engine_page_composition import build_poe2_follow_engine_page_adapter

    # Use importable fixture classes even after spawn prepares actual main.py.
    from tools.debug.follow_root_entry_probe import OfflineCaptureBackend as Backend, RecordingOutput as Output
    follower = "p2" if args.leader == "p1" else "p1"
    roles = {follower: 2 if follower == "p2" else 1}
    seed = FollowSeedBundle(
        map_instance="offline-map", roles=roles, observation_role_ids=("p1", "p2"),
        initial_positions_native={"p1": (529.0, 1088.0), "p2": (581.0, 1120.0)},
        initial_screen_positions={"p1": (30.0, 40.0), "p2": (82.0, 72.0)},
        transform=SimilarityTransform2D(0, False, 1.0, (499.0, 1048.0)),
    )
    mutex = None
    if sys.platform == "win32":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
        kernel.CreateMutexW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        mutex = kernel.CreateMutexW(None, False, bootstrap._single_instance_mutex_name())
        assert mutex
    adapter = composition = None
    outputs = []

    def output_factory(controller):
        output = Output(controller)
        outputs.append(output)
        return output

    try:
        sys.modules["__main__"].__file__ = str(root / "main.py")
        config = SimpleNamespace(binding=MonitorBinding(CaptureRect(0, 0, 120, 120)),
                                 localization_fps=30, recognizer_params={})
        adapter, composition = build_poe2_follow_engine_page_adapter(
            seed=seed, monitor_config=config, program_output_factory=output_factory,
            wall_map=np.zeros((2093, 2784), dtype=np.uint8),
            leader_role=args.leader, target_roles=(follower,),
            capture_backend_factory=Backend, arm_delay_ms=0,
        )
        start_at = time.perf_counter()
        adapter.start(FollowEngineStart(seed.map_instance, roles))
        startup_ms = (time.perf_counter() - start_at) * 1000
        deadline = time.monotonic() + 10
        seen = set()
        while time.monotonic() < deadline:
            state = adapter.poll()
            if state.diagnostics.get("last_error"):
                raise AssertionError(state.diagnostics)
            if state.snapshot is not None and set(state.snapshot.roles) == {"p1", "p2"}:
                assert {intent.role_id for intent in state.snapshot.output_intents} <= {follower}
                seen.add(state.snapshot.created_at_ms)
            if len(seen) >= 5 and outputs and any(v != (0.0, 0.0) for v, _ in outputs[0].writes):
                assert len(outputs) == 1 and outputs[0].controller == roles[follower]
                print(f"root_composition_ok leader={args.leader} follower={follower} startup_ms={startup_ms:.1f} snapshots={len(seen)}", flush=True)
                return
            time.sleep(0.01)
        raise AssertionError(f"no complete snapshot/output chain: {seen}, outputs={outputs}")
    finally:
        if adapter is not None:
            adapter.stop(reason="offline_probe")
        if composition is not None:
            composition.stop(reason="offline_probe")
        if mutex:
            kernel.CloseHandle(mutex)


if __name__ == "__main__":
    main()
