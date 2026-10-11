"""Bounded offline fault injection for follow lifecycle review; no real input.

The results describe current hazards, not passing acceptance of those hazards.
Each scenario runs in a disposable subprocess with an outer 15s watchdog.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
from pathlib import Path
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))


def hold_lock(lock, ready):
    lock.acquire()
    ready.set()
    time.sleep(10)


class FakeOutput:
    def __init__(self, *, fail_stop=False, slow_heartbeat=False):
        self.fail_stop = fail_stop
        self.slow_heartbeat = slow_heartbeat
        self.entered = threading.Event()
        self.release = threading.Event()
        self.stops = 0
        self.closes = 0

    def start(self):
        pass

    def write(self, _vector, *, elapsed_ms):
        pass

    def heartbeat(self):
        if self.slow_heartbeat:
            self.entered.set()
            self.release.wait(2)
        return True

    def stop(self):
        self.stops += 1
        if self.fail_stop:
            raise RuntimeError("offline stop failure")

    def close(self):
        self.closes += 1


def intents(*roles):
    return SimpleNamespace(output_intents=tuple(
        SimpleNamespace(role_id=role, controller=index + 1,
                        vector=(0.5, 0.0), duration_ms=20)
        for index, role in enumerate(roles)), session_active=True)


def ring_owner_death():
    from auto_modules.features.poe2.live_terrain.experimental.follow_engine.shared_frame_ring import SharedFrameRing
    ring = SharedFrameRing(slot_size=64)
    context = mp.get_context("spawn")
    ready = context.Event()
    process = context.Process(target=hold_lock, args=(ring._lock, ready))
    try:
        process.start()
        if not ready.wait(5):
            raise AssertionError("diagnostic lock holder did not start")
        process.terminate()
        process.join(2)
        acquired = ring._lock.acquire(timeout=0.2)
        if acquired:
            ring._lock.release()
        return {"lock_available_after_owner_terminate": acquired,
                "unbounded_ring_operations_would_wait": not acquired}
    finally:
        if process.is_alive():
            process.terminate()
            process.join(2)
        ring.close(unlink=True)


def failed_composition():
    from auto_modules.features.poe2.live_terrain.experimental.follow_engine import composition as module
    from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import SimilarityTransform2D
    made = []
    original = module.SharedFrameRing

    def recording_ring(**kwargs):
        ring = original(**kwargs)
        made.append(ring)
        return ring

    seed = module.FollowSeedBundle(
        map_instance="audit", roles={"p1": 1, "p2": 2},
        initial_positions_native={"p1": (10, 10), "p2": (20, 20)},
        initial_screen_positions={"p1": (10, 10), "p2": (20, 20)},
        transform=SimilarityTransform2D(0, False, 1, (0, 0)),
    )
    module.SharedFrameRing = recording_ring
    try:
        try:
            module.build_follow_engine_composition(
                seed=seed, capture=object(), output=object(),
                ring_slot_size=64, memory_source=object(),
            )
        except ValueError as exc:
            return {"error": str(exc), "rings_allocated": len(made),
                    "open_rings_after_constructor_failure": sum(r._shm is not None for r in made)}
        raise AssertionError("invalid memory pair unexpectedly accepted")
    finally:
        module.SharedFrameRing = original
        for ring in made:
            ring.close(unlink=True)


def failed_process_start():
    from auto_modules.features.poe2.live_terrain.experimental.follow_engine.control.follow_control_process import FollowControlProcessHandle
    handle = FollowControlProcessHandle({"p1": 1}, runtime_factory=lambda *_args: None)
    result = {}
    try:
        try:
            handle.start(generation=1, map_instance="audit")
        except Exception as exc:
            result["start_error"] = f"{type(exc).__name__}: {exc}"
        result["pid_after_start_failure"] = handle.process.pid if handle.process else None
        try:
            handle.stop(timeout=0)
        except Exception as exc:
            result["cleanup_error"] = f"{type(exc).__name__}: {exc}"
        result["process_reference_retained"] = handle.process is not None
        return result
    finally:
        process = handle.process
        if process is not None and process.pid is not None and process.is_alive():
            process.terminate()
            process.join(2)
        for channel in (handle.commands, handle.events):
            channel.cancel_join_thread()
            channel.close()


def failed_output_cleanup():
    from auto_modules.features.poe2.live_terrain.experimental.follow_engine.control.snapshot_output import SnapshotOutputAdapter
    first = FakeOutput(fail_stop=True)
    second = FakeOutput()
    adapter = SnapshotOutputAdapter({"p1": first, "p2": second})
    adapter.start()
    adapter.apply(intents("p1", "p2"))
    result = {}
    try:
        adapter.stop()
    except Exception as exc:
        result["cleanup_error"] = str(exc)
    result.update(first_stops=first.stops, second_stops=second.stops,
                  first_closes=first.closes, second_closes=second.closes,
                  adapter_started=adapter.started,
                  retained_roles=adapter.diagnostics()["roles"])
    first.fail_stop = False
    first.stop()
    second.stop()
    first.close()
    second.close()
    return result


def heartbeat_contention():
    from auto_modules.features.poe2.live_terrain.experimental.follow_engine.control.output_scheduler import OutputScheduler
    output = FakeOutput(slow_heartbeat=True)
    scheduler = OutputScheduler({"p1": output}, heartbeat_interval_ms=20)
    scheduler.start()
    scheduler.apply(intents("p1"))
    timer = None
    try:
        if not output.entered.wait(1):
            raise AssertionError("offline heartbeat not entered")
        timer = threading.Timer(0.3, output.release.set)
        timer.start()
        started = time.perf_counter()
        scheduler.diagnostics()
        return {"diagnostics_blocked_ms": round((time.perf_counter() - started) * 1000, 2)}
    finally:
        output.release.set()
        if timer is not None:
            timer.join(1)
        scheduler.stop()


def supervisor_start_failure():
    from auto_modules.features.poe2.live_terrain.experimental.follow_engine.process_supervisor import ProcessSupervisor
    from auto_modules.features.poe2.live_terrain.experimental.follow_engine.generation import GenerationToken
    calls = []

    def start(**kwargs):
        calls.append("allocated")
        raise RuntimeError("offline partial start failure")

    handle = SimpleNamespace(start=start, stop=lambda: calls.append("stopped"))
    supervisor = ProcessSupervisor(lambda: handle)
    try:
        supervisor.start(GenerationToken(1, "audit"))
    except RuntimeError:
        pass
    result = {"calls_after_failed_start": list(calls),
              "state": str(supervisor.status.state),
              "handle_retained": supervisor.handle is handle,
              "token_retained": supervisor.token is not None}
    supervisor.stop()
    return result


def unexecuted_command_prediction():
    from auto_modules.features.poe2.live_terrain.experimental.follow_engine.control.follow_control_process import FollowControlRuntime
    from auto_modules.features.poe2.live_terrain.experimental.follow_engine.control.snapshot_output import SnapshotOutputAdapter
    from auto_modules.features.poe2.live_terrain.experimental.follow_engine.contracts import (
        ObservationSource, RoleVisualObservation, VisualObservation,
    )
    from auto_modules.features.poe2.live_terrain.experimental.follow_engine.generation import GenerationToken
    now = [1000]
    outputs = []

    def factory(_role, _controller):
        output = FakeOutput()
        outputs.append(output)
        return output

    runtime = FollowControlRuntime(GenerationToken(1, "audit"), {"p2": 2})
    adapter = SnapshotOutputAdapter(output_factory=factory, arm_delay_ms=6000, clock_ms=lambda: now[0])
    runtime.apply_visual(VisualObservation(
        generation=1, sequence=1, captured_at_ms=1000, map_instance="audit",
        roles={"p2": RoleVisualObservation("p2", (0.0, 0.0), confidence=1.0,
                                          uncertainty_native=1.0, visible=True, last_visual_at_ms=1000)},
        source=ObservationSource.VISUAL,
    ))
    runtime.update_target("p2", (1000.0, 0.0))
    adapter.start()
    try:
        for timestamp in range(1000, 4001, 100):
            now[0] = timestamp
            snapshot = runtime.tick(now_ms=timestamp)
            adapter.apply(snapshot)
        return {"host_outputs_created": len(outputs),
                "predicted_position_during_arm_delay": snapshot.roles["p2"].position_native,
                "prediction_source": snapshot.roles["p2"].source,
                "remaining_arm_delay_ms": adapter.diagnostics()["arm_gate_remaining_ms"]}
    finally:
        adapter.stop()
        runtime.close()


SCENARIOS = {
    "ring_owner_death": ring_owner_death,
    "failed_composition": failed_composition,
    "failed_process_start": failed_process_start,
    "failed_output_cleanup": failed_output_cleanup,
    "heartbeat_contention": heartbeat_contention,
    "supervisor_start_failure": supervisor_start_failure,
    "unexecuted_command_prediction": unexecuted_command_prediction,
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=tuple(SCENARIOS))
    args = parser.parse_args()
    if args.scenario:
        print(json.dumps({"scenario": args.scenario, **SCENARIOS[args.scenario]()}, ensure_ascii=False))
        return
    for scenario in SCENARIOS:
        try:
            completed = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "--scenario", scenario],
                cwd=ROOT, capture_output=True, text=True, timeout=15,
            )
            print(completed.stdout.strip() or json.dumps({"scenario": scenario, "exit_code": completed.returncode}))
            if completed.returncode:
                print(completed.stderr[-1000:])
        except subprocess.TimeoutExpired:
            print(json.dumps({"scenario": scenario, "outer_watchdog": "timeout"}))


if __name__ == "__main__":
    mp.freeze_support()
    main()
