from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np


IMAGE_SUFFIX = ".png"


def main() -> None:
    args = parse_args()
    run_dir = resolve_path(args.run_dir, Path.cwd())
    out_dir = run_dir / "localization_audit"
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = audit_cases(run_dir, out_dir, label_filter=str(args.label))
    write_rows(out_dir / "detections.csv", rows)
    write_contact_sheet(out_dir / "detections_contact_sheet.png", rows)
    write_summary(out_dir / "summary.json", run_dir, rows)

    print(f"localization_audit: {out_dir}")
    print(f"detections: {len(rows)}")
    print(f"csv: {out_dir / 'detections.csv'}")
    print(f"contact_sheet: {out_dir / 'detections_contact_sheet.png'}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a visual audit sheet for loot detection localization.")
    parser.add_argument("--run-dir", required=True, help="debug/loot_dataset_eval/<run_id> directory containing cases.csv.")
    parser.add_argument("--label", default="has_loot", choices=("has_loot", "no_loot", "all"))
    return parser.parse_args()


def resolve_path(value: str, base: Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else base / path


def audit_cases(run_dir: Path, out_dir: Path, *, label_filter: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case in load_cases(run_dir):
        if label_filter != "all" and str(case.get("label")) != label_filter:
            continue
        image_path = Path(str(case.get("image", "")))
        if not image_path.is_file():
            continue
        frame = read_image(image_path)
        detections = list(case.get("detections") or [])
        if not detections:
            rows.append(empty_detection_row(case, image_path))
            continue
        for index, detection in enumerate(detections):
            metadata = dict(detection.get("metadata") or {})
            bbox = metadata.get("bbox") or [0, 0, 1, 1]
            x, y, width, height = clamp_bbox(frame.shape, bbox)
            crop = frame[y:y + height, x:x + width].copy()
            crop_path = out_dir / "crops" / f"{image_path.stem}__det{index:02d}.png"
            write_image(crop_path, crop)
            rows.append(
                {
                    "sample": image_path.name.split("__", 1)[0],
                    "image": str(image_path),
                    "label": str(case.get("label", "")),
                    "outcome": str(case.get("outcome", "")),
                    "det_index": int(index),
                    "confidence": float(detection.get("confidence", 0.0)),
                    "center": json.dumps(detection.get("local_minimap_pos"), ensure_ascii=False),
                    "bbox": json.dumps([x, y, width, height], ensure_ascii=False),
                    "template_score": float(metadata.get("template_score", 0.0)),
                    "shape_score": float(metadata.get("shape_score", 0.0)),
                    "color_score": float(metadata.get("color_score", 0.0)),
                    "templates": json.dumps(metadata.get("templates", []), ensure_ascii=False),
                    "crop": str(crop_path),
                }
            )
    return rows


def load_cases(run_dir: Path) -> list[dict[str, Any]]:
    summary_json = run_dir / "summary.json"
    if summary_json.is_file():
        with summary_json.open("r", encoding="utf-8") as handle:
            cases = json.load(handle).get("cases", [])
        return [dict(item) for item in cases]

    cases_csv = run_dir / "cases.csv"
    with cases_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(item) for item in csv.DictReader(handle)]


def empty_detection_row(case: dict[str, str], image_path: Path) -> dict[str, Any]:
    return {
        "sample": image_path.name.split("__", 1)[0],
        "image": str(image_path),
        "label": str(case.get("label", "")),
        "outcome": str(case.get("outcome", "")),
        "det_index": -1,
        "confidence": 0.0,
        "center": "",
        "bbox": "",
        "template_score": 0.0,
        "shape_score": 0.0,
        "color_score": 0.0,
        "templates": "",
        "crop": "",
    }


def clamp_bbox(shape, bbox: list[Any]) -> tuple[int, int, int, int]:
    height, width = shape[:2]
    x, y, box_w, box_h = [int(round(float(value))) for value in bbox[:4]]
    x = max(0, min(width - 1, x))
    y = max(0, min(height - 1, y))
    box_w = max(1, min(width - x, box_w))
    box_h = max(1, min(height - y, box_h))
    return x, y, box_w, box_h


def write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "sample",
        "label",
        "outcome",
        "det_index",
        "confidence",
        "center",
        "bbox",
        "template_score",
        "shape_score",
        "color_score",
        "templates",
        "image",
        "crop",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_summary(path: Path, run_dir: Path, rows: list[dict[str, Any]]) -> None:
    data = {
        "run_dir": str(run_dir),
        "detections": len([row for row in rows if int(row.get("det_index", -1)) >= 0]),
        "samples": len({str(row.get("sample", "")) for row in rows}),
        "outputs": {
            "detections_csv": str(path.parent / "detections.csv"),
            "contact_sheet": str(path.parent / "detections_contact_sheet.png"),
        },
    }
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def write_contact_sheet(path: Path, rows: list[dict[str, Any]]) -> None:
    detection_rows = [row for row in rows if int(row.get("det_index", -1)) >= 0 and row.get("crop")]
    if not detection_rows:
        return
    thumb = 116
    header = 54
    gap = 8
    columns = 5
    sheet_rows = int(np.ceil(len(detection_rows) / columns))
    sheet = np.full((sheet_rows * (thumb + header + gap) + gap, columns * (thumb + gap) + gap, 3), 28, dtype=np.uint8)

    for index, row in enumerate(detection_rows):
        crop = read_image(Path(str(row["crop"])))
        scale = min(thumb / crop.shape[1], thumb / crop.shape[0])
        resized = cv2.resize(
            crop,
            (max(1, int(round(crop.shape[1] * scale))), max(1, int(round(crop.shape[0] * scale)))),
            interpolation=cv2.INTER_NEAREST,
        )
        tile_x = gap + (index % columns) * (thumb + gap)
        tile_y = gap + (index // columns) * (thumb + header + gap)
        label = f"{row['sample']} #{row['det_index']} c={float(row['confidence']):.2f}"
        cv2.putText(sheet, label, (tile_x, tile_y + 17), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (240, 240, 240), 1, cv2.LINE_AA)
        label2 = f"t={float(row['template_score']):.2f} s={float(row['shape_score']):.2f}"
        cv2.putText(sheet, label2, (tile_x, tile_y + 37), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (210, 210, 210), 1, cv2.LINE_AA)
        image_x = tile_x + (thumb - resized.shape[1]) // 2
        image_y = tile_y + header + (thumb - resized.shape[0]) // 2
        sheet[image_y:image_y + resized.shape[0], image_x:image_x + resized.shape[1]] = resized
        cv2.rectangle(sheet, (image_x, image_y), (image_x + resized.shape[1] - 1, image_y + resized.shape[0] - 1), (60, 220, 60), 1)

    write_image(path, sheet)


def read_image(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(path)
    return image


def write_image(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(IMAGE_SUFFIX, image)
    if not ok:
        raise RuntimeError(f"failed to encode image: {path}")
    encoded.tofile(str(path))


if __name__ == "__main__":
    main()
