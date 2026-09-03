from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.events.types.loot.assets import LOOT_MINIMAP_TEMPLATES, LOOT_PLAYER_MARKER_EXCLUDE_TEMPLATES  # noqa: E402
from core.events.types.loot.config import LootEventConfig  # noqa: E402
from core.events.types.loot.detection.exclusions import (  # noqa: E402
    is_blue_map_artifact_candidate,
    is_player_marker_candidate,
    is_white_ring_map_artifact_candidate,
    player_marker_color_signature,
)
from core.events.types.loot.detection.images import pad_small_frame  # noqa: E402
from core.events.types.loot.detection.pipeline import _pad_bboxes, detect_loot_candidates, detect_loot_presence  # noqa: E402
from core.events.types.loot.detection.templates import load_loot_templates, prepare_scaled_templates  # noqa: E402


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


@dataclass(frozen=True)
class PresenceSample:
    features: np.ndarray
    diagnostics: dict[str, float | int | str]


def main() -> None:
    args = parse_args()
    dataset_root = resolve_path(args.dataset_root, Path.cwd())
    out_root = resolve_path(args.out_dir, PROJECT_ROOT)
    config = load_loot_config(resolve_path(args.map_config, PROJECT_ROOT))
    cv2.setRNGSeed(int(args.seed))
    evaluator = PresenceFeatureExtractor(config, feature_set=args.feature_set)
    cases = load_cases(dataset_root, args.positive_dir, args.negative_dir)
    samples = [evaluator.extract(path) for path, _ in cases]
    features = np.vstack([sample.features for sample in samples]).astype(np.float32)
    labels = np.array([label for _, label in cases], dtype=np.int32)
    names = [path.name for path, _ in cases]
    paths_by_name = {path.name: path for path, _ in cases}
    groups = [sample_group(name) for name in names]

    run_dir = out_root / datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)

    train_eval = evaluate_train_eval(features, labels, names, groups)
    cross_eval = evaluate_cross_validation(features, labels, names, groups, folds=int(args.folds), seed=int(args.seed))
    group_eval = evaluate_group_cross_validation(features, labels, names, groups)
    diagnostics = build_diagnostics_rows(samples, labels, names, groups)
    contact_outputs = write_contact_sheets(run_dir, paths_by_name, train_eval, cross_eval, group_eval)
    summary = {
        "dataset_root": str(dataset_root),
        "sample_totals": {
            "total": int(len(cases)),
            "has_loot": int(np.count_nonzero(labels == 1)),
            "no_loot": int(np.count_nonzero(labels == 0)),
        },
        "model": "opencv_rtrees_presence_probe",
        "feature_set": str(args.feature_set),
        "feature_count": int(features.shape[1]),
        "feature_groups": feature_group_descriptions(str(args.feature_set)),
        "groups": group_totals(groups, labels),
        "train_eval": train_eval["summary"],
        "cross_validation": cross_eval["summary"],
        "group_cross_validation": group_eval["summary"],
        "outputs": {
            "run_dir": str(run_dir),
            "summary_json": str(run_dir / "summary.json"),
            "train_cases_csv": str(run_dir / "train_eval_cases.csv"),
            "cv_cases_csv": str(run_dir / "cross_validation_cases.csv"),
            "group_cv_cases_csv": str(run_dir / "group_cross_validation_cases.csv"),
            "sample_diagnostics_csv": str(run_dir / "sample_diagnostics.csv"),
            **contact_outputs,
        },
    }
    write_json(run_dir / "summary.json", summary)
    write_cases_csv(run_dir / "train_eval_cases.csv", train_eval["cases"])
    write_cases_csv(run_dir / "cross_validation_cases.csv", cross_eval["cases"])
    write_cases_csv(run_dir / "group_cross_validation_cases.csv", group_eval["cases"])
    write_diagnostics_csv(run_dir / "sample_diagnostics.csv", diagnostics)

    if args.save_model:
        model, norm = train_model(features, labels)
        model_path = run_dir / "loot_presence_rtrees.yml"
        norm_path = run_dir / "loot_presence_norm.json"
        model.save(str(model_path))
        write_json(norm_path, {"mean": norm[0].tolist(), "std": norm[1].tolist()})
        summary["outputs"]["model"] = str(model_path)
        summary["outputs"]["normalization"] = str(norm_path)
        write_json(run_dir / "summary.json", summary)

    print_report(summary)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Image-level loot presence probe using dataset labels.")
    parser.add_argument("--dataset-root", default="D:/ACloud/image/sample")
    parser.add_argument("--positive-dir", default="02_has_loot")
    parser.add_argument("--negative-dir", default="03_no_loot")
    parser.add_argument("--map-config", default="map_data/A/event_config.json")
    parser.add_argument("--out-dir", default="debug/loot_presence_eval")
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--feature-set", choices=("baseline", "fusion"), default="baseline")
    parser.add_argument("--save-model", action="store_true")
    return parser.parse_args()


def resolve_path(value: str, base: Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else base / path


def load_loot_config(path: Path) -> LootEventConfig:
    with path.open("r", encoding="utf-8-sig") as handle:
        raw = json.load(handle).get("events", {}).get("loot", {})
    raw["diagnostic_capture_enabled"] = False
    raw["diagnostic_stage_dump_enabled"] = False
    return LootEventConfig.from_dict(raw)


def load_cases(root: Path, positive_dir: str, negative_dir: str) -> list[tuple[Path, int]]:
    positives = [(path, 1) for path in image_paths(root / positive_dir)]
    negatives = [(path, 0) for path in image_paths(root / negative_dir)]
    if not positives or not negatives:
        raise FileNotFoundError(f"expected positive and negative images under {root}")
    return positives + negatives


def image_paths(directory: Path) -> list[Path]:
    return sorted(
        [path for path in directory.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES],
        key=lambda item: item.name.lower(),
    )


def sample_group(name: str) -> str:
    match = re.match(r"^\d+__(.+?)__", name)
    return match.group(1) if match else "unknown"


def group_totals(groups: list[str], labels: np.ndarray) -> dict[str, dict[str, int]]:
    totals: dict[str, dict[str, int]] = {}
    for group, label in zip(groups, labels):
        row = totals.setdefault(group, {"total": 0, "has_loot": 0, "no_loot": 0})
        row["total"] += 1
        if int(label) == 1:
            row["has_loot"] += 1
        else:
            row["no_loot"] += 1
    return totals


def feature_group_descriptions(feature_set: str) -> list[str]:
    if feature_set == "fusion":
        return [
            "HSV color ratios by whole image and distance ring",
            "center-masked color ratios to reduce player arrow influence",
            "connected-component geometry for warm, neutral, and bright regions",
            "contour shape summaries for diamond/star-like color regions",
            "production candidate summaries containing template, shape, color, and exclusion signals",
        ]
    return [
        "HSV color ratios by whole image and distance ring",
        "warm color connected-component geometry",
        "production candidate summaries containing template, shape, color, and exclusion signals",
    ]


class PresenceFeatureExtractor:
    def __init__(self, config: LootEventConfig, *, feature_set: str = "baseline"):
        self.config = config
        self.feature_set = str(feature_set)
        self.templates = prepare_scaled_templates(load_loot_templates(LOOT_MINIMAP_TEMPLATES), config.scale_values())
        self.exclusion_templates = prepare_scaled_templates(
            load_loot_templates(LOOT_PLAYER_MARKER_EXCLUDE_TEMPLATES),
            config.scale_values(),
        )

    def extract(self, path: Path) -> PresenceSample:
        frame = read_image(path)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        height, width = frame.shape[:2]
        h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
        masks = {
            "gold": (h >= 14) & (h <= 50) & (s >= 55) & (v >= 85),
            "red": ((h <= 10) | (h >= 170)) & (s >= 60) & (v >= 90),
            "blue": (h >= 85) & (h <= 135) & (s >= 25) & (v >= 35) & (v <= 220),
            "neutral": (s <= 65) & (v >= 135),
            "bright": v >= 165,
        }
        warm_mask = masks["gold"] | masks["red"]
        loot_like_mask = warm_mask | masks["neutral"] | masks["bright"]

        base_features: list[float] = []
        fusion_only_features: list[float] = []
        diagnostics: dict[str, float | int | str] = {
            "width": int(width),
            "height": int(height),
        }
        yy, xx = np.indices((height, width))
        distance = np.sqrt((xx - width / 2.0) ** 2 + (yy - height / 2.0) ** 2)
        center_radius = max(0, int(getattr(self.config, "player_center_mask_radius", 28)))
        outside_player_center = distance > float(center_radius)
        for name, mask in masks.items():
            diagnostics[f"{name}_ratio"] = round(float(mask.mean()), 6)
            diagnostics[f"{name}_outside_center_ratio"] = round(float(mask[outside_player_center].mean()), 6)
            base_features.append(float(mask.mean()))
            fusion_only_features.append(float(mask[outside_player_center].mean()) if bool(outside_player_center.any()) else 0.0)
            for low, high in ((0, 30), (30, 60), (60, 100), (100, 200)):
                region = (distance >= low) & (distance < high)
                base_features.append(float(mask[region].mean()) if bool(region.any()) else 0.0)

        warm_component_features, warm_diag = component_features(warm_mask)
        warm_outer_features, warm_outer_diag = component_features(warm_mask & outside_player_center)
        neutral_outer_features, neutral_outer_diag = component_features(masks["neutral"] & outside_player_center)
        loot_like_outer_features, loot_like_outer_diag = component_features(loot_like_mask & outside_player_center)
        shape_features, shape_diag = contour_shape_features(warm_mask | (masks["neutral"] & outside_player_center))
        candidate_values, candidate_diag = candidate_features(frame, self.config, self.templates, self.exclusion_templates)

        if self.feature_set == "fusion":
            features = (
                base_features
                + fusion_only_features
                + warm_component_features
                + warm_outer_features
                + neutral_outer_features
                + loot_like_outer_features
                + shape_features
                + candidate_values
            )
        else:
            features = base_features + warm_component_features + candidate_values

        diagnostics.update(prefix_keys("warm", warm_diag))
        diagnostics.update(prefix_keys("warm_outer", warm_outer_diag))
        diagnostics.update(prefix_keys("neutral_outer", neutral_outer_diag))
        diagnostics.update(prefix_keys("loot_like_outer", loot_like_outer_diag))
        diagnostics.update(prefix_keys("shape", shape_diag))
        diagnostics.update(candidate_diag)
        return PresenceSample(features=np.array(features, dtype=np.float32), diagnostics=diagnostics)


def prefix_keys(prefix: str, values: dict[str, float | int | str]) -> dict[str, float | int | str]:
    return {f"{prefix}_{key}": value for key, value in values.items()}


def component_features(mask_bool: np.ndarray) -> tuple[list[float], dict[str, float | int]]:
    mask = (mask_bool.astype(np.uint8) * 255)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    components: list[tuple[float, float, float, float, float, float]] = []
    height, width = mask.shape[:2]
    for label in range(1, count):
        x = int(stats[label, cv2.CC_STAT_LEFT])
        y = int(stats[label, cv2.CC_STAT_TOP])
        w = int(stats[label, cv2.CC_STAT_WIDTH])
        h = int(stats[label, cv2.CC_STAT_HEIGHT])
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area < 8:
            continue
        components.append(
            (
                float(area),
                float(w),
                float(h),
                float(np.hypot(x + w / 2.0 - width / 2.0, y + h / 2.0 - height / 2.0)),
                float(max(w, h) / max(1, min(w, h))),
                float(area / max(1, w * h)),
            )
        )
    components.sort(key=lambda item: item[0], reverse=True)
    features: list[float] = [float(len(components)), float(sum(item[0] for item in components)), components[0][0] if components else 0.0]
    for index in range(8):
        features.extend(components[index] if index < len(components) else (0.0, 0.0, 0.0, 0.0, 0.0, 0.0))
    diagnostics = {
        "component_count": int(len(components)),
        "component_area_sum": int(sum(item[0] for item in components)),
        "largest_component_area": int(components[0][0]) if components else 0,
        "largest_component_distance": round(float(components[0][3]), 3) if components else 0.0,
    }
    return features, diagnostics


def contour_shape_features(mask_bool: np.ndarray) -> tuple[list[float], dict[str, float | int]]:
    mask = (mask_bool.astype(np.uint8) * 255)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    rows: list[tuple[float, float, float, float, float, float, float]] = []
    height, width = mask.shape[:2]
    for contour in contours:
        area = float(cv2.contourArea(contour))
        if area < 6.0:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        if w <= 0 or h <= 0:
            continue
        perimeter = float(cv2.arcLength(contour, True))
        approx = cv2.approxPolyDP(contour, 0.12 * perimeter, True) if perimeter > 0.0 else contour
        extent = float(area / max(1, w * h))
        aspect = float(max(w, h) / max(1, min(w, h)))
        circularity = float((4.0 * np.pi * area) / max(1e-6, perimeter * perimeter)) if perimeter > 0.0 else 0.0
        vertices = float(len(approx))
        distance = float(np.hypot(x + w / 2.0 - width / 2.0, y + h / 2.0 - height / 2.0))
        diamond_score = 0.0
        if 3.0 <= vertices <= 6.0 and 0.8 <= aspect <= 1.6 and 0.22 <= extent <= 0.72:
            diamond_score = 1.0 - min(1.0, abs(vertices - 4.0) / 3.0)
            diamond_score *= 1.0 - min(1.0, abs(aspect - 1.0) / 1.0)
            diamond_score *= 1.0 - min(1.0, abs(extent - 0.48) / 0.48)
        rows.append((area, float(w), float(h), distance, aspect, extent, circularity, vertices, diamond_score))
    rows.sort(key=lambda item: (item[8], item[0]), reverse=True)
    features: list[float] = [
        float(len(rows)),
        float(sum(item[0] for item in rows)),
        float(max((item[8] for item in rows), default=0.0)),
        float(sum(1 for item in rows if item[8] >= 0.20)),
    ]
    for index in range(8):
        features.extend(rows[index] if index < len(rows) else (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0))
    diagnostics = {
        "contour_count": int(len(rows)),
        "diamond_like_count": int(sum(1 for item in rows if item[8] >= 0.20)),
        "best_diamond_score": round(float(max((item[8] for item in rows), default=0.0)), 4),
        "best_contour_area": round(float(rows[0][0]), 3) if rows else 0.0,
        "best_contour_distance": round(float(rows[0][3]), 3) if rows else 0.0,
    }
    return features, diagnostics


def candidate_features(frame, config, templates, exclusion_templates) -> tuple[list[float], dict[str, float | int | str]]:
    height, width = frame.shape[:2]
    seeds = detect_loot_presence(frame, config, exclusion_templates)
    padded_frame, offset = pad_small_frame(frame, templates)
    candidates = detect_loot_candidates(padded_frame, templates, config, exclusion_templates, _pad_bboxes(seeds, offset))
    rows: list[list[float]] = []
    accepted_count = 0
    blue_excluded_count = 0
    white_excluded_count = 0
    player_excluded_count = 0
    best_template_name = ""
    for candidate in candidates:
        x = max(0, int(candidate.top_left[0]) - int(offset[0]))
        y = max(0, int(candidate.top_left[1]) - int(offset[1]))
        w, h = int(candidate.size[0]), int(candidate.size[1])
        w = min(w, width - x)
        h = min(h, height - y)
        if w <= 0 or h <= 0:
            continue
        patch = frame[y:y + h, x:x + w]
        signature = player_marker_color_signature(patch)
        blue_excluded, _ = is_blue_map_artifact_candidate(patch, candidate.shape_score)
        white_excluded, _ = is_white_ring_map_artifact_candidate(patch)
        player_excluded, _ = is_player_marker_candidate(patch, exclusion_templates, config)
        accepted_count += int(bool(candidate.accepted))
        blue_excluded_count += int(bool(blue_excluded))
        white_excluded_count += int(bool(white_excluded))
        player_excluded_count += int(bool(player_excluded))
        rows.append(
            [
                float(candidate.score),
                float(candidate.template_score),
                float(candidate.shape_score),
                float(candidate.color_score),
                float(signature["gold_ratio"]),
                float(signature["blue_ratio"]),
                float(signature["white_ratio"]),
                float(signature["bright_ratio"]),
                float(bool(blue_excluded)),
                float(bool(white_excluded)),
                float(bool(player_excluded)),
                float(bool(candidate.accepted)),
                float(np.hypot(x + w / 2.0 - width / 2.0, y + h / 2.0 - height / 2.0)),
            ]
        )
    rows.sort(key=lambda item: item[0], reverse=True)
    if candidates:
        best = sorted(candidates, key=lambda item: item.score, reverse=True)[0]
        best_template_name = str(best.template_name)
    features: list[float] = [float(len(rows)), float(sum(1 for item in rows if item[11] > 0.5))]
    for index in range(8):
        features.extend(rows[index] if index < len(rows) else [0.0] * 13)
    best_row = rows[0] if rows else [0.0] * 13
    diagnostics = {
        "seed_count": int(len(seeds)),
        "candidate_count": int(len(rows)),
        "accepted_candidate_count": int(accepted_count),
        "blue_excluded_count": int(blue_excluded_count),
        "white_excluded_count": int(white_excluded_count),
        "player_excluded_count": int(player_excluded_count),
        "best_candidate_score": round(float(best_row[0]), 4),
        "best_template_score": round(float(best_row[1]), 4),
        "best_shape_score": round(float(best_row[2]), 4),
        "best_color_score": round(float(best_row[3]), 4),
        "best_gold_ratio": round(float(best_row[4]), 4),
        "best_blue_ratio": round(float(best_row[5]), 4),
        "best_white_ratio": round(float(best_row[6]), 4),
        "best_bright_ratio": round(float(best_row[7]), 4),
        "best_center_distance": round(float(best_row[12]), 3),
        "best_template_name": best_template_name,
    }
    return features, diagnostics


def evaluate_train_eval(features: np.ndarray, labels: np.ndarray, names: list[str], groups: list[str]) -> dict:
    model, norm = train_model(features, labels)
    predictions = predict_model(model, normalize(features, norm))
    cases = build_cases(names, labels, predictions, groups, fold="train")
    return {"summary": summarize_cases(cases), "cases": cases}


def evaluate_cross_validation(
    features: np.ndarray,
    labels: np.ndarray,
    names: list[str],
    groups: list[str],
    *,
    folds: int,
    seed: int,
) -> dict:
    indices = list(range(len(labels)))
    random.Random(seed).shuffle(indices)
    split_count = max(2, int(folds))
    splits = [indices[index::split_count] for index in range(split_count)]
    all_predictions: dict[int, int] = {}
    for fold_index, test_indices in enumerate(splits):
        train_indices = [index for index in indices if index not in test_indices]
        predictions = fit_predict(features[train_indices], labels[train_indices], features[test_indices])
        for sample_index, prediction in zip(test_indices, predictions):
            all_predictions[int(sample_index)] = int(prediction)
    ordered_predictions = np.array([all_predictions[index] for index in range(len(labels))], dtype=np.int32)
    cases = build_cases(names, labels, ordered_predictions, groups, fold=f"{split_count}-fold")
    return {"summary": summarize_cases(cases), "cases": cases}


def evaluate_group_cross_validation(features: np.ndarray, labels: np.ndarray, names: list[str], groups: list[str]) -> dict:
    unique_groups = sorted(dict.fromkeys(groups))
    all_predictions: dict[int, int] = {}
    for group in unique_groups:
        test_indices = [index for index, value in enumerate(groups) if value == group]
        train_indices = [index for index, value in enumerate(groups) if value != group]
        predictions = fit_predict(features[train_indices], labels[train_indices], features[test_indices])
        for sample_index, prediction in zip(test_indices, predictions):
            all_predictions[int(sample_index)] = int(prediction)
    ordered_predictions = np.array([all_predictions[index] for index in range(len(labels))], dtype=np.int32)
    cases = [
        item
        for group in unique_groups
        for item in build_cases(
            [names[index] for index, value in enumerate(groups) if value == group],
            labels[[index for index, value in enumerate(groups) if value == group]],
            ordered_predictions[[index for index, value in enumerate(groups) if value == group]],
            [groups[index] for index, value in enumerate(groups) if value == group],
            fold=f"group:{group}",
        )
    ]
    return {"summary": summarize_cases(cases), "cases": cases}


def fit_predict(train_features: np.ndarray, train_labels: np.ndarray, test_features: np.ndarray) -> np.ndarray:
    unique_labels = np.unique(train_labels)
    if len(unique_labels) == 1:
        return np.full((len(test_features),), int(unique_labels[0]), dtype=np.int32)
    model, norm = train_model(train_features, train_labels)
    return predict_model(model, normalize(test_features, norm))


def train_model(features: np.ndarray, labels: np.ndarray):
    norm = normalization(features)
    train = normalize(features, norm)
    model = cv2.ml.RTrees_create()
    model.setMaxDepth(8)
    model.setMinSampleCount(2)
    model.setTermCriteria((cv2.TERM_CRITERIA_MAX_ITER, 80, 0))
    model.train(train, cv2.ml.ROW_SAMPLE, labels.astype(np.int32))
    return model, norm


def normalization(features: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mean = features.mean(axis=0)
    std = features.std(axis=0)
    std[std < 1e-6] = 1.0
    return mean.astype(np.float32), std.astype(np.float32)


def normalize(features: np.ndarray, norm: tuple[np.ndarray, np.ndarray]) -> np.ndarray:
    mean, std = norm
    return ((features - mean) / std).astype(np.float32)


def predict_model(model, features: np.ndarray) -> np.ndarray:
    _, prediction = model.predict(features)
    return np.array([1 if float(value) >= 0.5 else 0 for value in prediction.ravel()], dtype=np.int32)


def build_cases(names: list[str], labels: np.ndarray, predictions: np.ndarray, groups: list[str], *, fold: str) -> list[dict]:
    cases: list[dict] = []
    for name, expected, predicted, group in zip(names, labels, predictions, groups):
        expected_bool = bool(int(expected))
        predicted_bool = bool(int(predicted))
        if expected_bool and predicted_bool:
            outcome = "tp"
        elif expected_bool and not predicted_bool:
            outcome = "fn"
        elif not expected_bool and predicted_bool:
            outcome = "fp"
        else:
            outcome = "tn"
        cases.append(
            {
                "fold": fold,
                "group": group,
                "name": name,
                "expected": expected_bool,
                "predicted": predicted_bool,
                "outcome": outcome,
            }
        )
    return cases


def summarize_cases(cases: list[dict]) -> dict:
    counts = {name: sum(1 for item in cases if item["outcome"] == name) for name in ("tp", "fp", "fn", "tn")}
    total = len(cases)
    precision = ratio(counts["tp"], counts["tp"] + counts["fp"])
    recall = ratio(counts["tp"], counts["tp"] + counts["fn"])
    fpr = ratio(counts["fp"], counts["fp"] + counts["tn"])
    return {
        "counts": counts,
        "accuracy": ratio(counts["tp"] + counts["tn"], total),
        "precision": precision,
        "recall": recall,
        "false_positive_rate": fpr,
        "mismatches": [item for item in cases if item["outcome"] in {"fp", "fn"}],
    }


def ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(float(numerator) / float(denominator), 4)


def read_image(path: Path):
    image = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(path)
    return image


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def write_cases_csv(path: Path, cases: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["fold", "group", "name", "expected", "predicted", "outcome"])
        writer.writeheader()
        writer.writerows(cases)


def build_diagnostics_rows(samples: list[PresenceSample], labels: np.ndarray, names: list[str], groups: list[str]) -> list[dict]:
    rows: list[dict] = []
    for sample, label, name, group in zip(samples, labels, names, groups):
        rows.append(
            {
                "name": name,
                "group": group,
                "expected": bool(int(label)),
                **sample.diagnostics,
            }
        )
    return rows


def write_diagnostics_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_contact_sheets(
    run_dir: Path,
    paths_by_name: dict[str, Path],
    train_eval: dict,
    cross_eval: dict,
    group_eval: dict,
) -> dict[str, str]:
    outputs: dict[str, str] = {}
    targets = [
        ("train_mismatch_contact_sheet", train_eval["cases"], run_dir / "train_mismatch_contact_sheet.png"),
        ("cv_mismatch_contact_sheet", cross_eval["cases"], run_dir / "cv_mismatch_contact_sheet.png"),
        ("group_cv_mismatch_contact_sheet", group_eval["cases"], run_dir / "group_cv_mismatch_contact_sheet.png"),
    ]
    for key, cases, path in targets:
        written = write_mismatch_contact_sheet(path, cases, paths_by_name)
        if written is not None:
            outputs[key] = str(written)
    return outputs


def write_mismatch_contact_sheet(path: Path, cases: list[dict], paths_by_name: dict[str, Path]) -> Path | None:
    mismatches = [item for item in cases if item["outcome"] in {"fp", "fn"}]
    if not mismatches:
        return None
    thumb_w, thumb_h = 210, 210
    header_h = 34
    gap = 12
    columns = 3
    rows = int(np.ceil(len(mismatches) / columns))
    sheet_h = rows * (thumb_h + header_h + gap) + gap
    sheet_w = columns * (thumb_w + gap) + gap
    sheet = np.full((sheet_h, sheet_w, 3), 28, dtype=np.uint8)
    for index, item in enumerate(mismatches):
        image_path = paths_by_name.get(str(item["name"]))
        if image_path is None:
            continue
        image = read_image(image_path)
        tile_x = gap + (index % columns) * (thumb_w + gap)
        tile_y = gap + (index // columns) * (thumb_h + header_h + gap)
        label = f"{str(item['outcome']).upper()} {str(item['name']).split('__', 1)[0]}"
        cv2.putText(sheet, label, (tile_x, tile_y + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (235, 235, 235), 1, cv2.LINE_AA)
        scale = min(thumb_w / image.shape[1], thumb_h / image.shape[0])
        resized = cv2.resize(
            image,
            (max(1, int(round(image.shape[1] * scale))), max(1, int(round(image.shape[0] * scale)))),
            interpolation=cv2.INTER_AREA,
        )
        image_x = tile_x + (thumb_w - resized.shape[1]) // 2
        image_y = tile_y + header_h + (thumb_h - resized.shape[0]) // 2
        sheet[image_y:image_y + resized.shape[0], image_x:image_x + resized.shape[1]] = resized
        color = (80, 80, 255) if item["outcome"] == "fp" else (0, 180, 255)
        cv2.rectangle(sheet, (image_x, image_y), (image_x + resized.shape[1] - 1, image_y + resized.shape[0] - 1), color, 2)
    write_image(path, sheet)
    return path


def write_image(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, data = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError(f"failed to encode image: {path}")
    data.tofile(str(path))


def print_report(summary: dict) -> None:
    print("Loot presence probe complete")
    print(f"run_dir: {summary['outputs']['run_dir']}")
    for key in ("train_eval", "cross_validation", "group_cross_validation"):
        data = summary[key]
        counts = data["counts"]
        print(
            f"{key}: TP={counts['tp']} FP={counts['fp']} FN={counts['fn']} TN={counts['tn']} "
            f"precision={data['precision']} recall={data['recall']} fpr={data['false_positive_rate']} "
            f"accuracy={data['accuracy']}"
        )
        if data["mismatches"]:
            print(f"{key} mismatches: {len(data['mismatches'])}")
            for item in data["mismatches"][:12]:
                print(f"  {item['outcome'].upper()} {item['name']}")


if __name__ == "__main__":
    main()
