from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

import cv2
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.events.memory import EventMemory  # noqa: E402
from core.events.models import EventObservation, EventTask, EventTick  # noqa: E402
from core.events.types.loot import LootEventDefinition  # noqa: E402
from core.events.types.loot.assets import LOOT_MINIMAP_TEMPLATES, LOOT_PLAYER_MARKER_EXCLUDE_TEMPLATES  # noqa: E402
from core.events.types.loot.config import LootEventConfig  # noqa: E402
from core.events.types.loot.detection.images import pad_small_frame, unpad_bbox  # noqa: E402
from core.events.types.loot.detection.pipeline import _pad_bboxes, detect_loot_candidates, detect_loot_presence  # noqa: E402
from core.events.types.loot.detection.roi import apply_player_center_mask, build_loot_roi_mask  # noqa: E402
from core.events.types.loot.detection.templates import load_loot_templates, prepare_scaled_templates  # noqa: E402


def main() -> None:
    args = parse_args()
    config = config_from_args(args)
    results = []
    for image_path in input_images(args):
        result = run_detection_probe(image_path, config, Path(args.out_dir), dump_stages=bool(args.dump_stages))
        results.append(result)

    output = {
        "config": config.to_dict(),
        "images": results,
    }
    if args.benchmark:
        output["benchmark"] = run_detector_benchmark(config)
    if args.handler_smoke:
        output["handler_smoke"] = run_handler_smoke(config)
    if args.target_jitter_smoke:
        output["target_jitter_smoke"] = run_target_jitter_smoke(config)
    failures = validate_expectations(results, args)
    if args.target_jitter_smoke and not output["target_jitter_smoke"].get("target_locked"):
        failures.append("target jitter smoke: loot task target was not locked after confirmation")
    if failures:
        output["expectation_failures"] = failures
    print(json.dumps(output, ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe the production loot event detector and pickup handler.")
    parser.add_argument("--image", default="", help="Single minimap image to probe.")
    parser.add_argument("--test-dir", default="D:/ACloud/image/test", help="Directory of minimap images. Used when --image is empty.")
    parser.add_argument("--out-dir", default="debug/loot_event_probe", help="Output directory for overlays.")
    parser.add_argument("--threshold", type=float, default=0.54, help="Weighted detector threshold.")
    parser.add_argument("--collect-threshold", type=float, default=0.28, help="Loose candidate collection threshold.")
    parser.add_argument("--pickup-radius", type=int, default=58, help="Pickup radius used by handler smoke.")
    parser.add_argument("--arrival-radius", type=int, default=90, help="Arrival radius used by handler smoke.")
    parser.add_argument("--pickup-key", default="a", help="Pickup key used by handler smoke.")
    parser.add_argument("--presence-confirm-frames", type=int, default=2, help="Presence frames before full loot location.")
    parser.add_argument("--player-center-mask-radius", type=int, default=28, help="Fixed center player marker mask radius.")
    parser.add_argument("--dump-stages", action="store_true", help="Write raw mask, center-masked mask, seed, and candidate debug overlays.")
    parser.add_argument("--expect-count", type=int, default=None, help="Expected detection count for each probed image.")
    parser.add_argument("--expect-min-count", type=int, default=None, help="Minimum accepted detection count for each probed image.")
    parser.add_argument("--expect-center", default="", help="Expected first detection center as x,y.")
    parser.add_argument("--center-tolerance", type=float, default=10.0, help="Allowed pixel distance for --expect-center.")
    parser.add_argument("--benchmark", action="store_true", help="Run a small detector timing benchmark.")
    parser.add_argument("--handler-smoke", action="store_true", help="Also run move/press/complete handler smoke.")
    parser.add_argument("--target-jitter-smoke", action="store_true", help="Verify loot target locking under repeated drifting observations.")
    return parser.parse_args()


def config_from_args(args: argparse.Namespace) -> LootEventConfig:
    return LootEventConfig(
        weighted_threshold=float(args.threshold),
        collect_threshold=float(args.collect_threshold),
        pickup_radius=int(args.pickup_radius),
        arrival_radius=int(args.arrival_radius),
        pickup_key=str(args.pickup_key or "a"),
        presence_confirm_frames=int(args.presence_confirm_frames),
        player_center_mask_radius=int(args.player_center_mask_radius),
    )


def input_images(args: argparse.Namespace) -> list[Path]:
    if args.target_jitter_smoke and not args.image:
        return []
    if args.image:
        return [Path(args.image)]
    test_dir = Path(args.test_dir)
    return [
        path
        for path in sorted(test_dir.iterdir(), key=lambda item: item.name)
        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp"}
    ]


def run_detection_probe(image_path: Path, config: LootEventConfig, out_root: Path, dump_stages: bool = False) -> dict:
    definition = LootEventDefinition()
    detector = definition.create_detector(config.to_dict())
    frame = read_image(image_path)
    detections = []
    for index in range(max(1, int(config.presence_confirm_frames))):
        tick = EventTick(now_ms=1000 + index * 100, raw_minimap_frame=frame)
        detections = detector.detect(tick, config.to_dict())

    out_dir = out_root / image_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    overlay_path = out_dir / "loot_overlay.png"
    write_image(overlay_path, draw_overlay(frame.copy(), detections))

    result = {
        "image": str(image_path),
        "detection_count": len(detections),
        "detections": [detection_to_dict(detection) for detection in detections],
        "overlay": str(overlay_path),
    }
    if dump_stages:
        result["stages"] = dump_detection_stages(frame, config, out_dir)
    return result


def validate_expectations(results: list[dict], args: argparse.Namespace) -> list[str]:
    failures: list[str] = []
    expected_center = parse_center(args.expect_center)
    for result in results:
        count = int(result["detection_count"])
        image = str(result["image"])
        if args.expect_count is not None and count != int(args.expect_count):
            failures.append(f"{image}: expected detection_count={args.expect_count}, got {count}")
        if args.expect_min_count is not None and count < int(args.expect_min_count):
            failures.append(f"{image}: expected detection_count>={args.expect_min_count}, got {count}")
        if expected_center is not None:
            if not result["detections"]:
                failures.append(f"{image}: expected center {expected_center}, got no detections")
                continue
            actual = tuple(int(value) for value in result["detections"][0]["local_minimap_pos"])
            dist = float(np.hypot(actual[0] - expected_center[0], actual[1] - expected_center[1]))
            if dist > float(args.center_tolerance):
                failures.append(
                    f"{image}: expected center within {args.center_tolerance}px of {expected_center}, got {actual} dist={dist:.2f}"
                )
    return failures


def parse_center(value: str) -> tuple[int, int] | None:
    if not value:
        return None
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 2:
        raise ValueError("--expect-center must be formatted as x,y")
    return int(parts[0]), int(parts[1])


def dump_detection_stages(frame: np.ndarray, config: LootEventConfig, out_dir: Path) -> dict:
    templates = prepare_scaled_templates(load_loot_templates(LOOT_MINIMAP_TEMPLATES), config.scale_values())
    exclusion_templates = prepare_scaled_templates(
        load_loot_templates(LOOT_PLAYER_MARKER_EXCLUDE_TEMPLATES),
        config.scale_values(),
    )
    raw_mask = build_loot_roi_mask(frame)
    center_mask = apply_player_center_mask(raw_mask, frame, config, exclusion_templates)
    seeds = detect_loot_presence(frame, config, exclusion_templates)
    padded_frame, offset = pad_small_frame(frame, templates)
    padded_seeds = _pad_bboxes(seeds, offset)
    candidates = detect_loot_candidates(padded_frame, templates, config, exclusion_templates, padded_seeds)

    raw_mask_path = out_dir / "stage_raw_mask.png"
    center_mask_path = out_dir / "stage_center_mask.png"
    seed_overlay_path = out_dir / "stage_seed_overlay.png"
    candidate_overlay_path = out_dir / "stage_candidate_overlay.png"
    write_image(raw_mask_path, cv2.cvtColor(raw_mask, cv2.COLOR_GRAY2BGR))
    write_image(center_mask_path, cv2.cvtColor(center_mask, cv2.COLOR_GRAY2BGR))
    write_image(seed_overlay_path, draw_seed_overlay(frame.copy(), seeds))
    write_image(candidate_overlay_path, draw_candidate_overlay(frame.copy(), candidates, offset=offset))

    return {
        "raw_mask_pixels": int(np.count_nonzero(raw_mask)),
        "center_mask_pixels": int(np.count_nonzero(center_mask)),
        "seeds": [
            {
                "bbox": [int(seed[0]), int(seed[1]), int(seed[2]), int(seed[3])],
                "center": [int(seed[0] + seed[2] / 2), int(seed[1] + seed[3] / 2)],
            }
            for seed in seeds
        ],
        "candidate_count": len(candidates),
        "accepted_count": int(sum(1 for candidate in candidates if candidate.accepted)),
        "candidates": [
            candidate_to_stage_dict(candidate, offset, frame.shape)
            for candidate in candidates[:12]
        ],
        "raw_mask": str(raw_mask_path),
        "center_mask": str(center_mask_path),
        "seed_overlay": str(seed_overlay_path),
        "candidate_overlay": str(candidate_overlay_path),
    }


def candidate_to_stage_dict(candidate, offset: tuple[int, int], shape) -> dict:
    bbox = unpad_bbox(
        (
            int(candidate.top_left[0]),
            int(candidate.top_left[1]),
            int(candidate.size[0]),
            int(candidate.size[1]),
        ),
        offset,
        shape,
    )
    center = (
        max(0, min(int(shape[1]) - 1, int(candidate.center[0]) - int(offset[0]))),
        max(0, min(int(shape[0]) - 1, int(candidate.center[1]) - int(offset[1]))),
    )
    return {
        "score": round(float(candidate.score), 4),
        "template_score": round(float(candidate.template_score), 4),
        "shape_score": round(float(candidate.shape_score), 4),
        "color_score": round(float(candidate.color_score), 4),
        "accepted": bool(candidate.accepted),
        "template": candidate.template_name,
        "bbox": [int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])],
        "center": [int(center[0]), int(center[1])],
    }


def run_handler_smoke(config: LootEventConfig) -> list[dict]:
    definition = LootEventDefinition()
    task = EventTask(
        id="loot:smoke",
        event_type="loot",
        global_pos=(1000, 1000),
        first_seen_ms=1000,
        last_seen_ms=1000,
        priority=config.priority,
        confidence=0.8,
        metadata={"probe": True},
    )
    handler = definition.create_handler(config.to_dict())
    handler.start(task)

    steps = []
    far_tick = EventTick(now_ms=1100, raw_minimap_frame=np.zeros((120, 120, 3), dtype=np.uint8), player_global_pos=(850, 1000))
    steps.append(action_to_dict("far", handler.update(far_tick, task)))

    near_tick = EventTick(now_ms=1200, raw_minimap_frame=np.zeros((120, 120, 3), dtype=np.uint8), player_global_pos=(950, 1000))
    steps.append(action_to_dict("near", handler.update(near_tick, task)))

    after_press_tick = EventTick(now_ms=1300, raw_minimap_frame=np.zeros((120, 120, 3), dtype=np.uint8), player_global_pos=(950, 1000))
    steps.append(action_to_dict("post_press_wait", handler.update(after_press_tick, task)))

    absent_tick = EventTick(now_ms=1900, raw_minimap_frame=np.zeros((120, 120, 3), dtype=np.uint8), player_global_pos=(950, 1000))
    steps.append(action_to_dict("absent_complete", handler.update(absent_tick, task)))
    return steps


def run_target_jitter_smoke(config: LootEventConfig) -> dict:
    memory = EventMemory()
    event_config = config.to_dict()
    event_config["target_update_mode"] = "lock_after_confirm"
    event_config["memory_confirm_frames"] = 1
    fake_config = _SingleEventConfig("loot", event_config)
    positions = [(1000, 1000), (1035, 1000), (1088, 1015), (1010, 960)]
    snapshots = []
    for index, pos in enumerate(positions):
        now_ms = 1000 + index * 200
        memory.merge_observations(
            [
                EventObservation(
                    event_type="loot",
                    confidence=0.8,
                    observed_at_ms=now_ms,
                    global_pos=pos,
                    local_minimap_pos=(120 + index, 140),
                    source="target_jitter_smoke",
                    sample_count=2,
                    variance=10.0,
                    metadata={"pickup_radius": int(config.pickup_radius)},
                )
            ],
            fake_config,
            now_ms,
        )
        task = memory.tasks()[0]
        snapshots.append(
            {
                "observed_pos": list(pos),
                "task_global_pos": list(task.global_pos),
                "last_observed_global_pos": list(task.metadata.get("last_observed_global_pos", task.global_pos)),
                "state": getattr(task.state, "value", str(task.state)),
                "seen_count": int(task.seen_count),
                "target_update_reason": task.metadata.get("target_update_reason"),
                "target_drift": round(float(task.metadata.get("target_drift", 0.0)), 2),
            }
        )
    return {
        "mode": "lock_after_confirm",
        "initial_target": list(positions[0]),
        "final_target": list(memory.tasks()[0].global_pos),
        "target_locked": memory.tasks()[0].global_pos == positions[0],
        "snapshots": snapshots,
    }


class _SingleEventConfig:
    def __init__(self, event_type: str, event_config: dict):
        self.event_type = str(event_type)
        self.event_config = dict(event_config)

    def event(self, event_type: str) -> dict:
        if str(event_type) == self.event_type:
            return dict(self.event_config)
        return {}


def run_detector_benchmark(config: LootEventConfig) -> list[dict]:
    definition = LootEventDefinition()
    results: list[dict] = []
    for name, frame in benchmark_cases():
        detector = definition.create_detector(config.to_dict())
        for warmup_index in range(max(1, int(config.presence_confirm_frames))):
            detector.detect(EventTick(now_ms=1000 + warmup_index * 100, raw_minimap_frame=frame), config.to_dict())
        times = []
        counts = []
        for index in range(24):
            tick = EventTick(now_ms=1000 + index * 100, raw_minimap_frame=frame)
            start = cv2.getTickCount()
            detections = detector.detect(tick, config.to_dict())
            elapsed_ms = (cv2.getTickCount() - start) * 1000.0 / cv2.getTickFrequency()
            if index >= 4:
                times.append(float(elapsed_ms))
                counts.append(int(len(detections)))
        results.append(
            {
                "case": name,
                "shape": list(frame.shape),
                "avg_ms": round(float(sum(times) / max(1, len(times))), 2),
                "max_ms": round(float(max(times) if times else 0.0), 2),
                "detection_counts": sorted(set(counts)),
            }
        )
    return results


def benchmark_cases() -> list[tuple[str, np.ndarray]]:
    positive = read_image(Path("D:/ACloud/image/test/620a06ae5e363165b735820e99ea4d8e.png"))
    blank300 = np.full((300, 300, 3), 49, dtype=np.uint8)
    positive300 = blank300.copy()
    h, w = positive.shape[:2]
    positive300[92:92 + h, 172:172 + w] = positive

    player300 = blank300.copy()
    player_path = Path("D:/ACloud/image/人物/0b799b87-9b87-4458-b026-5d7df13da763.png")
    if player_path.is_file():
        player = read_image(player_path)
        ph, pw = player.shape[:2]
        player300[130:130 + ph, 130:130 + pw] = player

    return [
        ("positive_tiny", positive),
        ("blank300", blank300),
        ("positive300", positive300),
        ("player300", player300),
    ]


def action_to_dict(step: str, action) -> dict:
    return {
        "step": step,
        "type": getattr(getattr(action, "type", None), "value", str(getattr(action, "type", ""))),
        "key": getattr(action, "key", None),
        "target_global_pos": getattr(action, "target_global_pos", None),
        "wait_ms": getattr(action, "wait_ms", None),
        "reason": getattr(action, "reason", ""),
        "metadata": getattr(action, "metadata", {}),
    }


def detection_to_dict(detection) -> dict:
    data = asdict(detection)
    data["event_type"] = str(data["event_type"])
    return data


def read_image(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise FileNotFoundError(f"image not readable: {path}")
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.shape[2] == 4:
        return image[:, :, :3]
    return image[:, :, :3]


def write_image(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(path.suffix or ".png", image)
    if not ok:
        raise RuntimeError(f"failed to encode image: {path}")
    encoded.tofile(str(path))


def draw_overlay(frame: np.ndarray, detections: list) -> np.ndarray:
    for detection in detections:
        metadata = dict(detection.metadata or {})
        x, y, w, h = [int(value) for value in metadata.get("bbox", [0, 0, 1, 1])]
        center = (int(detection.local_minimap_pos[0]), int(detection.local_minimap_pos[1]))
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
        cv2.circle(frame, center, 4, (0, 0, 255), -1)
        cv2.putText(
            frame,
            f"loot {float(detection.confidence):.2f}",
            (x, min(frame.shape[0] - 5, y + h + 14)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            (0, 0, 255),
            1,
            cv2.LINE_AA,
        )
    return frame


def draw_seed_overlay(frame: np.ndarray, seeds: list[tuple[int, int, int, int]]) -> np.ndarray:
    for index, (x, y, w, h) in enumerate(seeds):
        cv2.rectangle(frame, (int(x), int(y)), (int(x + w), int(y + h)), (0, 255, 255), 2)
        cv2.putText(
            frame,
            f"seed {index}",
            (int(x), max(12, int(y) - 4)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            (0, 255, 255),
            1,
            cv2.LINE_AA,
        )
    return frame


def draw_candidate_overlay(frame: np.ndarray, candidates: list, offset: tuple[int, int] = (0, 0)) -> np.ndarray:
    for candidate in candidates[:12]:
        x = int(candidate.top_left[0]) - int(offset[0])
        y = int(candidate.top_left[1]) - int(offset[1])
        w, h = candidate.size
        if x + int(w) <= 0 or y + int(h) <= 0 or x >= frame.shape[1] or y >= frame.shape[0]:
            continue
        x = max(0, int(x))
        y = max(0, int(y))
        w = max(1, min(int(w), int(frame.shape[1]) - x))
        h = max(1, min(int(h), int(frame.shape[0]) - y))
        color = (0, 0, 255) if candidate.accepted else (0, 165, 255)
        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
        cv2.putText(
            frame,
            f"{candidate.score:.2f} {candidate.template_name[:4]}",
            (x, min(frame.shape[0] - 5, y + h + 13)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.38,
            color,
            1,
            cv2.LINE_AA,
        )
    return frame


if __name__ == "__main__":
    main()
