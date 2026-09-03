from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import cv2
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.events.models import EventTick  # noqa: E402
from core.events.types.loot import LootEventDefinition  # noqa: E402
from core.events.types.loot.config import LootEventConfig  # noqa: E402


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


def main() -> None:
    args = parse_args()
    dataset_root = resolve_path(args.dataset_root, Path.cwd())
    out_root = resolve_path(args.out_dir, PROJECT_ROOT)
    map_config_path = resolve_path(args.map_config, PROJECT_ROOT) if args.map_config else None
    config, config_source = load_config(args, map_config_path)
    if not args.show_event_log:
        silence_loot_event_logs()

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = out_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    cases = dataset_cases(dataset_root, args.positive_dir, args.negative_dir, int(args.limit or 0))
    results = [evaluate_case(case, config, run_dir, dump_all=bool(args.dump_all)) for case in cases]
    summary = build_summary(
        run_id=run_id,
        dataset_root=dataset_root,
        map_config_path=map_config_path,
        config=config,
        config_source=config_source,
        results=results,
        run_dir=run_dir,
        args=args,
    )
    cases_csv = run_dir / "cases.csv"
    summary_json = run_dir / "summary.json"
    write_cases_csv(cases_csv, results)
    summary["outputs"]["cases_csv"] = str(cases_csv)
    summary["outputs"]["summary_json"] = str(summary_json)
    write_json(summary_json, summary)

    print_summary(summary)
    if args.strict and (summary["counts"]["fp"] or summary["counts"]["fn"]):
        raise SystemExit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate the production loot minimap detector on a labeled dataset.")
    parser.add_argument("--dataset-root", default="D:/ACloud/image/sample", help="Dataset root containing positive/negative folders.")
    parser.add_argument("--positive-dir", default="02_has_loot", help="Folder name for samples expected to contain loot.")
    parser.add_argument("--negative-dir", default="03_no_loot", help="Folder name for samples expected to contain no loot.")
    parser.add_argument("--map-config", default="map_data/A/event_config.json", help="Runtime event_config.json to load loot params from.")
    parser.add_argument("--out-dir", default="debug/loot_dataset_eval", help="Output root for evaluation runs.")
    parser.add_argument("--threshold", type=float, default=None, help="Override weighted_threshold.")
    parser.add_argument("--collect-threshold", type=float, default=None, help="Override collect_threshold.")
    parser.add_argument("--presence-confirm-frames", type=int, default=None, help="Override presence_confirm_frames.")
    parser.add_argument("--player-center-mask-radius", type=int, default=None, help="Override player_center_mask_radius.")
    parser.add_argument("--max-blobs-per-frame", type=int, default=None, help="Override max_blobs_per_frame.")
    parser.add_argument("--dump-all", action="store_true", help="Write overlays for correct cases too, not only FP/FN.")
    parser.add_argument("--enable-runtime-diagnostics", action="store_true", help="Keep LootDiagnosticCapture enabled from map config.")
    parser.add_argument("--show-event-log", action="store_true", help="Print production event_log lines while evaluating.")
    parser.add_argument("--limit", type=int, default=0, help="Limit images per label folder. 0 means all.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when any false positive or false negative exists.")
    return parser.parse_args()


def silence_loot_event_logs() -> None:
    import core.events.types.loot.minimap_detector as minimap_detector

    minimap_detector.event_log = lambda *args, **kwargs: None


def resolve_path(value: str, relative_base: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return relative_base / path


def load_config(args: argparse.Namespace, map_config_path: Path | None) -> tuple[LootEventConfig, dict[str, Any]]:
    raw_config: dict[str, Any] = {}
    source: dict[str, Any] = {"kind": "defaults"}
    if map_config_path is not None and map_config_path.is_file():
        with map_config_path.open("r", encoding="utf-8-sig") as handle:
            config_doc = json.load(handle)
        raw_config = dict(config_doc.get("events", {}).get("loot", {}))
        source = {"kind": "map_config", "path": str(map_config_path)}
    elif map_config_path is not None:
        source = {"kind": "defaults", "missing_map_config": str(map_config_path)}

    if not args.enable_runtime_diagnostics:
        raw_config["diagnostic_capture_enabled"] = False
        raw_config["diagnostic_stage_dump_enabled"] = False
    apply_overrides(raw_config, args)
    return LootEventConfig.from_dict(raw_config), source


def apply_overrides(config: dict[str, Any], args: argparse.Namespace) -> None:
    override_map = {
        "threshold": "weighted_threshold",
        "collect_threshold": "collect_threshold",
        "presence_confirm_frames": "presence_confirm_frames",
        "player_center_mask_radius": "player_center_mask_radius",
        "max_blobs_per_frame": "max_blobs_per_frame",
    }
    for arg_name, config_name in override_map.items():
        value = getattr(args, arg_name, None)
        if value is not None:
            config[config_name] = value


def dataset_cases(root: Path, positive_dir: str, negative_dir: str, limit: int) -> list[dict[str, Any]]:
    positive_paths = image_paths(root / positive_dir)
    negative_paths = image_paths(root / negative_dir)
    if limit > 0:
        positive_paths = positive_paths[:limit]
        negative_paths = negative_paths[:limit]
    if not positive_paths and not negative_paths:
        raise FileNotFoundError(f"no image samples found under {root}")
    return [
        {"path": path, "label": "has_loot", "expected": True}
        for path in positive_paths
    ] + [
        {"path": path, "label": "no_loot", "expected": False}
        for path in negative_paths
    ]


def image_paths(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(
        [path for path in directory.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES],
        key=lambda path: path.name.lower(),
    )


def evaluate_case(case: dict[str, Any], config: LootEventConfig, run_dir: Path, *, dump_all: bool) -> dict[str, Any]:
    image_path = Path(case["path"])
    read_start = perf_counter()
    frame = read_image(image_path)
    read_ms = elapsed_ms(read_start)

    detector = LootEventDefinition().create_detector(config.to_dict())
    detect_start = perf_counter()
    detections = []
    confirm_frames = max(1, int(config.presence_confirm_frames))
    for index in range(confirm_frames):
        tick = EventTick(now_ms=1000 + index * 100, raw_minimap_frame=frame)
        detections = detector.detect(tick, config.to_dict())
    detect_ms = elapsed_ms(detect_start)

    predicted = bool(detections)
    expected = bool(case["expected"])
    outcome = classify_outcome(expected, predicted)
    detection_dicts = [detection_to_dict(detection) for detection in detections]
    best = best_detection(detection_dicts)

    overlay_path = ""
    if dump_all or outcome in {"fp", "fn"}:
        overlay_dir = run_dir / "overlays" / outcome
        overlay_name = f"{image_path.stem}__{outcome}.png"
        overlay_path = str(overlay_dir / overlay_name)
        write_image(Path(overlay_path), draw_overlay(frame.copy(), detections, expected, predicted, outcome, detect_ms))

    return {
        "image": str(image_path),
        "name": image_path.name,
        "label": str(case["label"]),
        "expected": expected,
        "predicted": predicted,
        "outcome": outcome,
        "detection_count": int(len(detections)),
        "best_confidence": best.get("confidence"),
        "best_center": best.get("local_minimap_pos"),
        "best_bbox": best.get("bbox"),
        "best_template_score": best.get("template_score"),
        "best_shape_score": best.get("shape_score"),
        "best_color_score": best.get("color_score"),
        "best_templates": best.get("templates"),
        "detections": detection_dicts,
        "read_ms": round(float(read_ms), 3),
        "detect_ms": round(float(detect_ms), 3),
        "overlay": overlay_path,
    }


def classify_outcome(expected: bool, predicted: bool) -> str:
    if expected and predicted:
        return "tp"
    if expected and not predicted:
        return "fn"
    if not expected and predicted:
        return "fp"
    return "tn"


def detection_to_dict(detection: Any) -> dict[str, Any]:
    data = asdict(detection)
    metadata = dict(data.get("metadata") or {})
    data["metadata"] = metadata
    data["confidence"] = round(float(data.get("confidence", 0.0)), 6)
    return data


def best_detection(detections: list[dict[str, Any]]) -> dict[str, Any]:
    if not detections:
        return {}
    detection = max(detections, key=lambda item: float(item.get("confidence", 0.0)))
    metadata = dict(detection.get("metadata") or {})
    return {
        "confidence": float(detection.get("confidence", 0.0)),
        "local_minimap_pos": detection.get("local_minimap_pos"),
        "bbox": metadata.get("bbox"),
        "template_score": metadata.get("template_score"),
        "shape_score": metadata.get("shape_score"),
        "color_score": metadata.get("color_score"),
        "templates": metadata.get("templates"),
    }


def build_summary(
    *,
    run_id: str,
    dataset_root: Path,
    map_config_path: Path | None,
    config: LootEventConfig,
    config_source: dict[str, Any],
    results: list[dict[str, Any]],
    run_dir: Path,
    args: argparse.Namespace,
) -> dict[str, Any]:
    counts = {name: sum(1 for item in results if item["outcome"] == name) for name in ("tp", "fp", "fn", "tn")}
    pos_total = sum(1 for item in results if item["expected"])
    neg_total = sum(1 for item in results if not item["expected"])
    total = len(results)
    detect_times = [float(item["detect_ms"]) for item in results]
    metrics = {
        "accuracy": ratio(counts["tp"] + counts["tn"], total),
        "precision": ratio(counts["tp"], counts["tp"] + counts["fp"]),
        "recall": ratio(counts["tp"], counts["tp"] + counts["fn"]),
        "false_positive_rate": ratio(counts["fp"], counts["fp"] + counts["tn"]),
        "false_negative_rate": ratio(counts["fn"], counts["fn"] + counts["tp"]),
    }
    return {
        "run_id": run_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "dataset_root": str(dataset_root),
        "map_config": str(map_config_path) if map_config_path is not None else "",
        "config_source": config_source,
        "config": config.to_dict(),
        "cli": {
            "dump_all": bool(args.dump_all),
            "strict": bool(args.strict),
            "limit_per_label": int(args.limit or 0),
            "enable_runtime_diagnostics": bool(args.enable_runtime_diagnostics),
        },
        "sample_totals": {
            "total": total,
            "has_loot": pos_total,
            "no_loot": neg_total,
        },
        "counts": counts,
        "metrics": metrics,
        "timing": timing_summary(detect_times),
        "mismatches": [item for item in results if item["outcome"] in {"fp", "fn"}],
        "cases": results,
        "outputs": {
            "run_dir": str(run_dir),
            "overlays_dir": str(run_dir / "overlays"),
        },
    }


def ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(float(numerator) / float(denominator), 4)


def timing_summary(values: list[float]) -> dict[str, float]:
    if not values:
        return {"avg_ms": 0.0, "p50_ms": 0.0, "p95_ms": 0.0, "max_ms": 0.0}
    ordered = sorted(values)
    return {
        "avg_ms": round(sum(values) / len(values), 3),
        "p50_ms": round(percentile(ordered, 50), 3),
        "p95_ms": round(percentile(ordered, 95), 3),
        "max_ms": round(max(values), 3),
    }


def percentile(ordered_values: list[float], percentile_value: int) -> float:
    if not ordered_values:
        return 0.0
    index = int(round((len(ordered_values) - 1) * (percentile_value / 100.0)))
    index = max(0, min(len(ordered_values) - 1, index))
    return float(ordered_values[index])


def write_cases_csv(path: Path, results: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "label",
        "expected",
        "predicted",
        "outcome",
        "detection_count",
        "best_confidence",
        "best_center",
        "best_bbox",
        "best_template_score",
        "best_shape_score",
        "best_color_score",
        "best_templates",
        "detect_ms",
        "read_ms",
        "image",
        "overlay",
    ]
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in results:
            writer.writerow({field: csv_value(item.get(field)) for field in fields})


def csv_value(value: Any) -> Any:
    if isinstance(value, (list, dict, tuple)):
        return json.dumps(value, ensure_ascii=False)
    return value


def print_summary(summary: dict[str, Any]) -> None:
    counts = summary["counts"]
    metrics = summary["metrics"]
    timing = summary["timing"]
    print("Loot dataset evaluation complete")
    print(f"run_dir: {summary['outputs']['run_dir']}")
    print(
        "samples: "
        f"total={summary['sample_totals']['total']} "
        f"has_loot={summary['sample_totals']['has_loot']} "
        f"no_loot={summary['sample_totals']['no_loot']}"
    )
    print(f"counts: TP={counts['tp']} FP={counts['fp']} FN={counts['fn']} TN={counts['tn']}")
    print(
        "metrics: "
        f"precision={format_metric(metrics['precision'])} "
        f"recall={format_metric(metrics['recall'])} "
        f"fpr={format_metric(metrics['false_positive_rate'])} "
        f"accuracy={format_metric(metrics['accuracy'])}"
    )
    print(
        "timing: "
        f"avg={timing['avg_ms']}ms "
        f"p50={timing['p50_ms']}ms "
        f"p95={timing['p95_ms']}ms "
        f"max={timing['max_ms']}ms"
    )
    if summary["mismatches"]:
        print(f"mismatches: {len(summary['mismatches'])}")
        for item in summary["mismatches"][:10]:
            print(f"  {item['outcome'].upper()} {item['name']} count={item['detection_count']} conf={item['best_confidence']}")
    print(f"summary_json: {summary['outputs'].get('summary_json', '')}")
    print(f"cases_csv: {summary['outputs'].get('cases_csv', '')}")


def format_metric(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.4f}"


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


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def elapsed_ms(start: float) -> float:
    return (perf_counter() - start) * 1000.0


def draw_overlay(
    frame: np.ndarray,
    detections: list[Any],
    expected: bool,
    predicted: bool,
    outcome: str,
    detect_ms: float,
) -> np.ndarray:
    color = (0, 0, 255) if outcome in {"fp", "fn"} else (0, 180, 0)
    for detection in detections:
        metadata = dict(getattr(detection, "metadata", {}) or {})
        x, y, w, h = [int(value) for value in metadata.get("bbox", [0, 0, 1, 1])]
        center = (int(detection.local_minimap_pos[0]), int(detection.local_minimap_pos[1]))
        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
        cv2.circle(frame, center, 4, color, -1)
        label = (
            f"{float(detection.confidence):.2f} "
            f"t={float(metadata.get('template_score', 0.0)):.2f} "
            f"s={float(metadata.get('shape_score', 0.0)):.2f} "
            f"c={float(metadata.get('color_score', 0.0)):.2f}"
        )
        cv2.putText(
            frame,
            label,
            (x, min(frame.shape[0] - 5, y + h + 14)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            color,
            1,
            cv2.LINE_AA,
        )
    status = f"{outcome.upper()} expected={int(expected)} predicted={int(predicted)} {detect_ms:.1f}ms"
    cv2.rectangle(frame, (0, 0), (min(frame.shape[1], 360), 22), (0, 0, 0), -1)
    cv2.putText(frame, status, (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
    return frame


if __name__ == "__main__":
    main()
