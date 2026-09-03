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

from core.platform import SquareScreenCapture
from core.events.detectors.template_matcher import TemplateMatchHit, load_template, match_single_template, merge_hits
from core.events.types.portal.assets import PORTAL_MINIMAP_TEMPLATES
from core.events.types.portal.minimap_feature_matcher import build_feature_templates, match_portal_features
from core.events.types.portal.minimap_hit_filter import portal_color_check
from core.events.types.portal.minimap_shape_color import (
    PortalShapeColorParams,
    match_portal_shape_color,
)


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
    parser.add_argument("--image", action="append", help="Use an existing minimap image instead of live capture. Can be repeated.")
    parser.add_argument("--threshold", type=float, default=0.72, help="Minimum combined match score to mark a hit.")
    parser.add_argument("--color-threshold", type=float, default=0.08, help="Runtime portal blue-ratio threshold.")
    parser.add_argument("--portal-feature-detector", action="store_true", help="Use the portal blue-feature detector instead of full-image template matching.")
    parser.add_argument("--portal-shape-color-detector", action="store_true", help="Use the stricter portal shape+color detector.")
    parser.add_argument("--feature-hue-min", type=int, default=82, help="Portal feature HSV hue minimum.")
    parser.add_argument("--feature-hue-max", type=int, default=136, help="Portal feature HSV hue maximum.")
    parser.add_argument("--feature-sat-min", type=int, default=55, help="Portal feature HSV saturation minimum.")
    parser.add_argument("--feature-val-min", type=int, default=95, help="Portal feature HSV value minimum.")
    parser.add_argument("--feature-min-blue-pixels", type=int, default=36, help="Minimum blue-feature pixels inside a portal candidate.")
    parser.add_argument("--feature-max-blue-pixels", type=int, default=420, help="Maximum blue-feature pixels inside a portal candidate; 0 disables the cap.")
    parser.add_argument("--shape-outer-sat-max", type=int, default=115, help="Maximum saturation for portal white/gray outer ring pixels.")
    parser.add_argument("--shape-outer-val-min", type=int, default=105, help="Minimum value for portal white/gray outer ring pixels.")
    parser.add_argument("--shape-min-blue-score", type=float, default=0.28, help="Minimum blue-core shape F1 score.")
    parser.add_argument("--shape-min-outer-score", type=float, default=0.18, help="Minimum white/gray outer-ring shape F1 score.")
    parser.add_argument("--shape-min-shape-score", type=float, default=0.30, help="Minimum combined shape F1 score.")
    parser.add_argument("--shape-min-outer-pixels", type=int, default=14, help="Minimum white/gray outer pixels inside a candidate bbox.")
    parser.add_argument("--shape-signature-min-outer-score", type=float, default=0.45, help="Signature path minimum outer-ring score.")
    parser.add_argument("--shape-signature-min-edge-score", type=float, default=0.40, help="Signature path minimum edge score.")
    parser.add_argument("--shape-signature-min-color-score", type=float, default=0.82, help="Signature path minimum HSV color score.")
    parser.add_argument("--shape-signature-score-scale", type=float, default=1.30, help="Signature path score multiplier.")
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


def draw_shape_color_hits(frame, hits: list):
    debug = frame.copy()
    for index, hit in enumerate(hits, start=1):
        x, y = hit.top_left
        w, h = hit.size
        color = (0, 255, 0) if hit.accepted else (0, 180, 255)
        cv2.rectangle(debug, (x, y), (x + w, y + h), color, 2)
        cv2.circle(debug, hit.center, 3, color, -1)
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


def print_hit(prefix: str, hit) -> None:
    print(
        f"{prefix} "
        f"template={hit.template_name} "
        f"score={hit.score:.4f} "
        f"gray={float(getattr(hit, 'gray_score', 0.0)):.4f} "
        f"edge={float(getattr(hit, 'edge_score', 0.0)):.4f} "
        f"mask={float(getattr(hit, 'mask_score', hit.score)):.4f} "
        f"density={float(getattr(hit, 'density_score', 0.0)):.4f} "
        f"scale={hit.scale:.2f} top_left={hit.top_left} center={hit.center} size={hit.size}"
    )


def print_shape_color_hit(prefix: str, hit) -> None:
    state = "accepted" if hit.accepted else "rejected"
    reasons = ",".join(hit.reject_reasons) if hit.reject_reasons else "-"
    print(
        f"{prefix} {state} "
        f"template={hit.template_name} score={hit.score:.4f} "
        f"blue={hit.blue_score:.4f} outer={hit.outer_score:.4f} "
        f"shape={hit.shape_score:.4f} edge={hit.edge_score:.4f} "
        f"color={hit.color_score:.4f} response={hit.response_score:.4f} "
        f"scale={hit.scale:.2f} top_left={hit.top_left} center={hit.center} size={hit.size} "
        f"blue_pixels={hit.blue_pixels}/{hit.template_blue_pixels} "
        f"outer_pixels={hit.outer_pixels}/{hit.template_outer_pixels} "
        f"reasons={reasons}"
    )


def print_portal_color(prefix: str, frame, hit: TemplateMatchHit, min_blue_ratio: float) -> None:
    color = portal_color_check(frame, hit, min_blue_ratio)
    state = "color-ok" if color["accepted"] else "color-rejected"
    print(
        f"{prefix} {state} "
        f"blue_ratio={float(color['blue_ratio']):.4f} "
        f"blue_pixels={int(color['blue_pixels'])} "
        f"min_blue_ratio={float(min_blue_ratio):.4f}"
    )


def save_image(path: Path, image) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), image)


def save_shape_color_crops(frame, hits: list, output_dir: Path, suffix: str) -> None:
    crop_dir = output_dir / "shape_color_candidates"
    crop_dir.mkdir(parents=True, exist_ok=True)
    for index, hit in enumerate(hits, start=1):
        x, y = hit.top_left
        w, h = hit.size
        pad = max(3, int(round(min(w, h) * 0.2)))
        left = max(0, x - pad)
        top = max(0, y - pad)
        right = min(frame.shape[1], x + w + pad)
        bottom = min(frame.shape[0], y + h + pad)
        crop = frame[top:bottom, left:right]
        if crop.size == 0:
            continue
        state = "accepted" if hit.accepted else "rejected"
        path = crop_dir / f"{suffix}_{index:02d}_{state}_{hit.template_name}_{hit.center[0]}_{hit.center[1]}.png"
        save_image(path, crop)


def probe_frame(frame, *, output_dir: Path, suffix: str, templates: list, scales: list[float], args) -> None:
    raw_path = output_dir / f"minimap_raw_{suffix}.png"
    save_image(raw_path, frame)
    print(f"[probe] saved raw={raw_path}")

    if not templates or args.save_frame_only:
        return

    if args.portal_shape_color_detector:
        params = PortalShapeColorParams(
            threshold=float(args.threshold),
            hue_min=int(args.feature_hue_min),
            hue_max=int(args.feature_hue_max),
            sat_min=int(args.feature_sat_min),
            val_min=int(args.feature_val_min),
            outer_sat_max=int(args.shape_outer_sat_max),
            outer_val_min=int(args.shape_outer_val_min),
            min_blue_pixels=int(args.feature_min_blue_pixels),
            max_blue_pixels=int(args.feature_max_blue_pixels),
            min_outer_pixels=int(args.shape_min_outer_pixels),
            min_blue_score=float(args.shape_min_blue_score),
            min_outer_score=float(args.shape_min_outer_score),
            min_shape_score=float(args.shape_min_shape_score),
            signature_min_outer_score=float(args.shape_signature_min_outer_score),
            signature_min_edge_score=float(args.shape_signature_min_edge_score),
            signature_min_color_score=float(args.shape_signature_min_color_score),
            signature_score_scale=float(args.shape_signature_score_scale),
        )
        hits, debug_masks = match_portal_shape_color(
            frame,
            templates,
            scales,
            top_k=int(args.top_k),
            params=params,
        )
        debug = draw_shape_color_hits(frame, hits)
        debug_path = output_dir / f"minimap_portal_shape_color_{suffix}.png"
        save_image(debug_path, debug)
        save_image(output_dir / f"minimap_portal_shape_blue_mask_{suffix}.png", debug_masks.frame_blue_mask)
        save_image(output_dir / f"minimap_portal_shape_outer_mask_{suffix}.png", debug_masks.frame_outer_mask)
        save_image(output_dir / f"minimap_portal_shape_combined_mask_{suffix}.png", debug_masks.frame_shape_mask)
        save_shape_color_crops(frame, hits, output_dir, suffix)
        print(f"[probe] saved shape_color_debug={debug_path}")
        print(
            f"[probe] portal shape+color templates={len(templates)} "
            f"threshold={float(args.threshold):.2f} "
            f"hue=[{int(args.feature_hue_min)},{int(args.feature_hue_max)}] "
            f"sat_min={int(args.feature_sat_min)} val_min={int(args.feature_val_min)} "
            f"outer_sat_max={int(args.shape_outer_sat_max)} outer_val_min={int(args.shape_outer_val_min)} "
            f"blue_pixels=[{int(args.feature_min_blue_pixels)},{int(args.feature_max_blue_pixels)}] "
            f"signature=edge>={float(args.shape_signature_min_edge_score):.2f},"
            f"color>={float(args.shape_signature_min_color_score):.2f},"
            f"outer>={float(args.shape_signature_min_outer_score):.2f}"
        )
        if hits:
            accepted = [hit for hit in hits if hit.accepted]
            if accepted:
                print_shape_color_hit("[probe] shape-color-best", accepted[0])
            else:
                print(f"[probe] no accepted shape+color hit above threshold={args.threshold:.2f}")
            for hit in hits:
                print_shape_color_hit("[probe] shape-color-candidate", hit)
        else:
            print(f"[probe] no shape+color candidate above collection threshold")
        return

    if args.portal_feature_detector:
        feature_templates = build_feature_templates(
            templates,
            hue_min=int(args.feature_hue_min),
            hue_max=int(args.feature_hue_max),
            sat_min=int(args.feature_sat_min),
            val_min=int(args.feature_val_min),
        )
        hits = match_portal_features(
            frame,
            feature_templates,
            scales,
            top_k=int(args.top_k),
            threshold=float(args.threshold),
            hue_min=int(args.feature_hue_min),
            hue_max=int(args.feature_hue_max),
            sat_min=int(args.feature_sat_min),
            val_min=int(args.feature_val_min),
            min_blue_pixels=int(args.feature_min_blue_pixels),
            max_blue_pixels=int(args.feature_max_blue_pixels),
        )
        debug = draw_hits(frame, hits, args.threshold)
        debug_path = output_dir / f"minimap_portal_feature_{suffix}.png"
        save_image(debug_path, debug)
        print(f"[probe] saved feature_debug={debug_path}")
        print(
            f"[probe] portal feature templates={len(feature_templates)} "
            f"threshold={float(args.threshold):.2f} "
            f"hue=[{int(args.feature_hue_min)},{int(args.feature_hue_max)}] "
            f"sat_min={int(args.feature_sat_min)} val_min={int(args.feature_val_min)} "
            f"blue_pixels=[{int(args.feature_min_blue_pixels)},{int(args.feature_max_blue_pixels)}]"
        )
        if hits:
            for hit in hits:
                print_hit("[probe] feature-hit", hit)
                print_portal_color("[probe] feature-hit", frame, hit, args.color_threshold)
        else:
            print(f"[probe] no portal feature hit above threshold={args.threshold:.2f}")
        return

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
        print_portal_color("[probe] best", frame, best, args.color_threshold)
        for hit in hits:
            print_hit("[probe] hit", hit)
            print_portal_color("[probe] hit", frame, hit, args.color_threshold)
    else:
        print(f"[probe] no accepted hit above threshold={args.threshold:.2f}")
    for hit in template_best_hits:
        state = "accepted" if hit.score >= args.threshold else "below-threshold"
        print_hit(f"[probe] template-best {state}", hit)
        print_portal_color(f"[probe] template-best {state}", frame, hit, args.color_threshold)


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
    if (args.portal_feature_detector or args.portal_shape_color_detector) and not args.template:
        args.template = [str(path) for path in PORTAL_MINIMAP_TEMPLATES]
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
    if args.image:
        for image_index, raw_image_path in enumerate(args.image, start=1):
            image_path = Path(raw_image_path)
            if not image_path.is_absolute():
                image_path = ROOT / image_path
            frame = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
            if frame is None:
                print(f"[probe] image not readable: {image_path}")
                continue
            print(f"[probe] image={image_path} size={frame.shape[1]}x{frame.shape[0]}")
            stamp = time.strftime("%Y%m%d_%H%M%S")
            suffix = f"image_{image_index:02d}_{stamp}"
            probe_frame(frame, output_dir=output_dir, suffix=suffix, templates=templates, scales=scales, args=args)
        return 0

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
            probe_frame(frame, output_dir=output_dir, suffix=suffix, templates=templates, scales=scales, args=args)

            if index + 1 < max(1, int(args.repeat)):
                time.sleep(max(0.0, float(args.interval)))
    finally:
        capture.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
