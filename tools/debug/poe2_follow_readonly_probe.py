"""有限次数的 PoE2 双人跟随链只读实机探针。

这个工具用于验证最近的首帧/视觉跟踪/后台状态链，不发送任何鼠标、键盘、
手柄或网络输入。它只做以下事情：

* 读取当前 PoE2 进程一次并在本项目目录保存同一实例的 native terrain；
* 使用当前 PoE2 monitor profile 截取有限数量的小地图帧；
* 调用正式双人定位 composition，记录首帧结果、后续视觉状态和分阶段耗时；
* 保存少量原始截图，方便把“识别失败”和“界面/捕获慢”分开判断。

如果进程拒绝只读句柄，工具会把真实的权限错误保存到报告并返回非零，绝不
尝试提权、重试输入或启动跟随运行器。
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
from typing import Any, Mapping

import cv2
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
RESEARCH_ROOT = Path("D:/ACloud/poe2-map-research")
for _path in (PROJECT_ROOT, SRC_ROOT, RESEARCH_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from windows_capture import (  # type: ignore[import-not-found]  # noqa: E402
    capture_descriptor,
    find_process_id,
    resolve_poe2_descriptor,
)

from auto_modules.adapters.platform.screen_capture import SquareScreenCapture  # noqa: E402
from auto_modules.features.poe2.live_terrain import (  # noqa: E402
    MonitorFrameSource,
    Poe2MonitorProfileStore,
)
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization.composition import (  # noqa: E402
    build_poe2_dual_localization_experiment,
)
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization.memory_anchors import (  # noqa: E402
    Poe2DualPlayerPositionSource,
)
from auto_modules.features.poe2.live_terrain.terrain_reference import build_reference  # noqa: E402
from auto_modules.features.poe2.live_terrain.native_grid import load_native_grid  # noqa: E402
from auto_modules.core.vision import HSVRecognizer  # noqa: E402


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if is_dataclass(value):
        return asdict(value)  # type: ignore[arg-type]
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, (tuple, list)):
        return list(value)
    return str(value)


def _state_payload(state: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for name in (
        "status", "reason", "source", "confidence", "wall_quality",
        "recovery_requested", "recovery_revision", "players", "screen_positions",
        "diagnostics",
    ):
        if hasattr(state, name):
            payload[name] = getattr(state, name)
    return json.loads(json.dumps(payload, default=_json_default))


def _save_frame(path: Path, frame: Any) -> None:
    array = np.asarray(frame)
    if array.size == 0 or array.ndim not in (2, 3):
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), array)


def _capture_terrain(run_root: Path) -> tuple[Any, dict[str, Any]]:
    """Read and export one guarded terrain snapshot into the local worktree."""
    pid = find_process_id()
    descriptor = resolve_poe2_descriptor(pid, stage="readonly-follow-probe")
    terrain_dir = run_root / "terrain_capture"
    # ``capture_descriptor`` creates and atomically publishes its output
    # directory itself.  Creating it here first makes the producer fail with
    # WinError 183 before any terrain bytes are read.
    terrain_dir.parent.mkdir(parents=True, exist_ok=True)
    capture_result = capture_descriptor(descriptor, terrain_dir)
    native_path = terrain_dir / "export" / "native_grid.npz"
    snapshot = load_native_grid(native_path)
    return snapshot, {
        "pid": pid,
        "descriptor": descriptor,
        "capture_result": capture_result,
        "native_grid": str(native_path),
    }


def run_probe(
    *,
    output_root: str | Path,
    frame_count: int = 12,
    interval_seconds: float = 0.10,
    save_frames: int = 6,
) -> dict[str, Any]:
    if not 1 <= int(frame_count) <= 60:
        raise ValueError("frame_count must be between 1 and 60")
    if not 0.0 <= float(interval_seconds) <= 2.0:
        raise ValueError("interval_seconds must be between 0 and 2")
    root = Path(output_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:-3]
    run_root = root / stamp
    run_root.mkdir(parents=True)
    report: dict[str, Any] = {
        "schema_version": 1,
        "tool": "poe2-follow-readonly-probe",
        "read_only": True,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "limits": {
            "frame_count": int(frame_count),
            "interval_seconds": float(interval_seconds),
            "save_frames": int(save_frames),
            "input_calls": 0,
            "network_calls": 0,
        },
        "run_root": str(run_root),
        "steps": [],
        "frames": [],
        "errors": [],
    }
    started = time.perf_counter()
    capture_backend: SquareScreenCapture | None = None
    experiment = None
    try:
        step_started = time.perf_counter()
        snapshot, terrain_details = _capture_terrain(run_root)
        report["terrain"] = {
            "metadata": dict(snapshot.metadata.extra),
            "area_id": snapshot.metadata.area_id,
            "instance_id": snapshot.metadata.instance_id,
            "shape": [snapshot.metadata.height, snapshot.metadata.width],
            "details": terrain_details,
        }
        report["steps"].append({
            "name": "terrain_read",
            "elapsed_ms": (time.perf_counter() - step_started) * 1000.0,
            "instance_id": snapshot.metadata.instance_id,
        })

        profile_store = Poe2MonitorProfileStore(PROJECT_ROOT / "data" / "poe2_live_terrain" / "monitor_profiles")
        config = profile_store.active()
        if config is None or config.binding is None:
            raise RuntimeError("当前 PoE2 monitor profile 没有有效截图绑定")
        report["monitor_config"] = config.as_dict()
        capture_backend = SquareScreenCapture()
        frame_source = MonitorFrameSource(capture_backend)
        recognizer = HSVRecognizer()
        if config.recognizer_params:
            recognizer.set_params(dict(config.recognizer_params))
        source = Poe2DualPlayerPositionSource()

        def capture(config_value: Any) -> Any:
            return frame_source.capture(
                config_value.binding,
                shape=config_value.shape,
                radius=config_value.circle_radius,
            )

        def config_provider() -> Any:
            return config

        experiment = build_poe2_dual_localization_experiment(
            snapshot=snapshot,
            config_provider=config_provider,
            preview_capture=capture,
            recognizer=recognizer,
            dual_player_position_source=source,
        )
        experiment.session.start()
        for index in range(int(frame_count)):
            tick_started = time.perf_counter()
            state = experiment.session.tick()
            timing = dict(experiment.session.last_timing_ms)
            item: dict[str, Any] = {
                "index": index,
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "state": _state_payload(state),
                "timing_ms": timing,
                "frame_age_ms": None,
            }
            raw = experiment.session.last_raw_frame
            frame_timestamp = getattr(experiment.session.last_frame, "captured_at_ms", None)
            if frame_timestamp is not None:
                item["frame_timestamp_ms"] = int(frame_timestamp)
                item["frame_age_ms"] = max(0, int(time.time() * 1000) - int(frame_timestamp))
            if raw is not None and index < int(save_frames):
                frame_path = run_root / "frames" / f"frame-{index:03d}.png"
                _save_frame(frame_path, raw)
                item["raw_frame"] = str(frame_path)
            report["frames"].append(item)
            report["steps"].append({
                "name": "session_tick",
                "index": index,
                "elapsed_ms": (time.perf_counter() - tick_started) * 1000.0,
                "timing_ms": timing,
                "status": getattr(state, "status", None),
                "reason": getattr(state, "reason", None),
            })
            if not bool(getattr(state, "status", "").startswith("tracking")) and index == 0:
                # Do not repeatedly read memory when the initial registration failed.
                break
            if index + 1 < int(frame_count):
                time.sleep(float(interval_seconds))
        experiment.session.stop()
    except Exception as exc:  # noqa: BLE001 - report the exact live boundary failure
        report["errors"].append({
            "type": type(exc).__name__,
            "message": str(exc),
        })
    finally:
        if capture_backend is not None:
            capture_backend.close()
    report["elapsed_ms"] = (time.perf_counter() - started) * 1000.0
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    report_path = run_root / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=_json_default) + "\n", encoding="utf-8")
    latest = root / "latest.json"
    latest.write_text(report_path.read_text(encoding="utf-8"), encoding="utf-8")
    report["report"] = str(report_path)
    return report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(PROJECT_ROOT / "data" / "poe2_live_terrain_test" / "readonly_follow_probes"))
    parser.add_argument("--frames", type=int, default=12)
    parser.add_argument("--interval", type=float, default=0.10)
    parser.add_argument("--save-frames", type=int, default=6)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = run_probe(
            output_root=args.out,
            frame_count=args.frames,
            interval_seconds=args.interval,
            save_frames=args.save_frames,
        )
    except Exception as exc:  # argument/serialization failures
        print(json.dumps({"tool": "poe2-follow-readonly-probe", "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False))
        return 2
    print(json.dumps({
        "report": result.get("report"),
        "instance_id": result.get("terrain", {}).get("instance_id"),
        "frames": len(result.get("frames", [])),
        "states": [item.get("state", {}).get("status") for item in result.get("frames", [])],
        "errors": result.get("errors", []),
        "input_calls": result.get("limits", {}).get("input_calls"),
    }, ensure_ascii=False, indent=2))
    return 0 if not result.get("errors") else 1


if __name__ == "__main__":
    raise SystemExit(main())
