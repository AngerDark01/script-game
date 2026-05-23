"""Standalone probe for minimap event icon template matching.

This script is intentionally not wired into navigation. It validates whether a
saved event icon template can be found in the raw minimap capture configured by
a map folder such as map_data/A1.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.capture import SquareScreenCapture
from core.events.detectors.template_matcher import TemplateMatchHit, load_template, match_single_template, merge_hits


@dataclass
class CaptureGeometry:
    rect: dict
    player_local_pos: tuple[int, int] | None
    dpr: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe minimap event icon matching.")
    parser.add_argument("--map-folder", default="map_data/A1", help="Map folder containing config.json.")
    parser.add_argument("--template", action="append", help="Template image path for the minimap icon. Can be repeated.")
    parser.add_argument("--output-dir", default="debug/event_probe", help="Directory for captures and debug images.")
    parser.add_argument("--threshold", type=float, default=0.72, help="Minimum combined match score to mark a hit.")
    parser.add_argument("--scales", default="0.75,0.85,1.0,1.15,1.3", help="Comma-separated template scales.")
    parser.add_argument("--top-k", type=int, default=8, help="Maximum number of matches to report.")
    parser.add_argument("--repeat", type=int, default=1, help="Number of captures to probe.")
    parser.add_argument("--interval", type=float, default=0.2, help="Seconds between repeated captures.")
    parser.add_argument("--dpr", type=float, help="Override device pixel ratio.")
    parser.add_argument("--save-frame-only", action="store_true", help="Only save raw minimap captures.")
    return parser.parse_args()


def load_config(map_folder: Path) -> dict:
    config_path = map_folder / "config.json"
    with config_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def get_device_pixel_ratio(override: float | None = None) -> float:
    if override and override > 0:
        return float(override)
    try:
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        screen = app.primaryScreen()
        if screen:
            dpr = float(screen.devicePixelRatio())
            if dpr > 0:
                return dpr
    except Exception:
        pass
    return 1.0


def build_capture_geometry(config: dict, dpr: float) -> CaptureGeometry:
    region = config.get("monitor_region")
    if region:
        rect = {
            "left": int(region["left"]),
            "top": int(region["top"]),
            "width": int(region["width"]),
            "height": int(region["height"]),
        }
        return CaptureGeometry(rect=rect, player_local_pos=None, dpr=dpr)

    center = config.get("monitor_logical_center") or config.get("monitor_center")
    size = int(config.get("monitor_size", 0) or 0)
    if not center or size <= 0:
        raise ValueError("config.json lacks monitor_region or monitor_logical_center/monitor_size")

    center_x = int(float(center[0]) * dpr)
    center_y = int(float(center[1]) * dpr)
    half = size // 2
    rect = {
        "left": center_x - half,
        "top": center_y - half,
        "width": size,
        "height": size,
    }
    return CaptureGeometry(rect=rect, player_local_pos=(size // 2, size // 2), dpr=dpr)


def parse_scales(raw: str) -> list[float]:
    scales = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        value = float(part)
        if value > 0:
            scales.append(value)
    return scales or [1.0]


def draw_hits(frame, hits: list, threshold: float):
    debug = frame.copy()
    for index, hit in enumerate(hits, start=1):
        x, y = hit.top_left
        w, h = hit.size
        color = (0, 255, 0) if hit.score >= threshold else (0, 180, 255)
        cv2.rectangle(debug, (x, y), (x + w, y + h), color, 2)
        cv2.putText(
            debug,
            f"{index}:{hit.score:.2f}",
            (x, max(12, y - 4)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            color,
            1,
            cv2.LINE_AA,
        )
    return debug


def print_hit(prefix: str, hit: TemplateMatchHit) -> None:
    print(
        f"{prefix} "
        f"template={hit.template_name} "
        f"score={hit.score:.4f} gray={hit.gray_score:.4f} edge={hit.edge_score:.4f} "
        f"scale={hit.scale:.2f} top_left={hit.top_left} center={hit.center} size={hit.size}"
    )


def save_image(path: Path, image) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), image)


def main() -> int:
    args = parse_args()
    map_folder = Path(args.map_folder)
    if not map_folder.is_absolute():
        map_folder = ROOT / map_folder
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    config = load_config(map_folder)
    dpr = get_device_pixel_ratio(args.dpr)
    geometry = build_capture_geometry(config, dpr)
    print(f"[probe] map_folder={map_folder}")
    print(f"[probe] dpr={geometry.dpr:.3f} rect={geometry.rect} player_local={geometry.player_local_pos}")

    templates = []
    if args.template:
        for raw_template_path in args.template:
            template_path = Path(raw_template_path)
            if not template_path.is_absolute():
                template_path = ROOT / template_path
            template = load_template(template_path)
            templates.append(template)
            print(f"[probe] template={template_path} size={template.image.shape[1]}x{template.image.shape[0]} mask={template.mask is not None}")
    elif not args.save_frame_only:
        print("[probe] no --template supplied; saving raw captures only")

    scales = parse_scales(args.scales)
    capture = SquareScreenCapture()
    try:
        for index in range(max(1, int(args.repeat))):
            frame = capture.capture(
                geometry.rect["left"],
                geometry.rect["top"],
                geometry.rect["width"],
                geometry.rect["height"],
            )
            stamp = time.strftime("%Y%m%d_%H%M%S")
            suffix = f"{stamp}_{index + 1:02d}"
            raw_path = output_dir / f"minimap_raw_{suffix}.png"
            save_image(raw_path, frame)
            print(f"[probe] saved raw={raw_path}")

            if templates and not args.save_frame_only:
                raw_hits: list[TemplateMatchHit] = []
                template_best_hits: list[TemplateMatchHit] = []
                for template_spec in templates:
                    template_hits = match_single_template(
                        frame,
                        template_spec,
                        scales,
                        args.top_k,
                        args.threshold,
                    )
                    raw_hits.extend(template_hits)

                    if template_hits:
                        template_best_hits.append(template_hits[0])
                    else:
                        diagnostic_hits = match_single_template(
                            frame,
                            template_spec,
                            scales,
                            1,
                            -1.0,
                        )
                        if diagnostic_hits:
                            template_best_hits.append(diagnostic_hits[0])

                hits = merge_hits(raw_hits, args.top_k)
                debug_hits = hits if hits else merge_hits(template_best_hits, args.top_k)
                debug = draw_hits(frame, debug_hits, args.threshold)
                debug_path = output_dir / f"minimap_match_{suffix}.png"
                save_image(debug_path, debug)
                print(f"[probe] saved debug={debug_path}")
                if hits:
                    best = hits[0]
                    print_hit("[probe] best", best)
                    for hit in hits:
                        print_hit("[probe] hit", hit)
                else:
                    print(f"[probe] no accepted hit above threshold={args.threshold:.2f}")
                for hit in template_best_hits:
                    state = "accepted" if hit.score >= args.threshold else "below-threshold"
                    print_hit(f"[probe] template-best {state}", hit)

            if index + 1 < max(1, int(args.repeat)):
                time.sleep(max(0.0, float(args.interval)))
    finally:
        capture.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
