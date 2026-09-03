"""Standalone probe for detecting portal candidates in the main game view.

This script is intentionally not wired into navigation. It captures the game
window or an explicit screen rectangle, extracts blue/cyan portal-like glowing
regions, and saves annotated debug images so the detection approach can be
validated before being integrated as an event handler.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.platform import SquareScreenCapture
from core.events.window_finder import find_game_window, primary_screen_rect, set_process_dpi_awareness
from core.events.types.portal.main_view_confirmer import (
    PortalMainViewCandidate,
    build_blue_glow_mask,
    detect_portal_candidates,
    is_strict_portal_candidate,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe portal detection in the main game view.")
    parser.add_argument("--output-dir", default="debug/portal_screen_probe", help="Directory for raw and debug images.")
    parser.add_argument("--params", help="JSON parameter asset to load detector thresholds from.")
    parser.add_argument("--window-title", default="Torchlight", help="Substring used to find the game window.")
    parser.add_argument("--window-class", default="UnrealWindow", help="Class substring used to find the game window.")
    parser.add_argument("--rect", help="Explicit capture rect: left,top,width,height. Overrides window search.")
    parser.add_argument("--full-screen", action="store_true", help="Capture the primary screen instead of the game window.")
    parser.add_argument("--save-frame-only", action="store_true", help="Only save the captured raw frame.")
    parser.add_argument("--repeat", type=int, default=1, help="Number of captures to probe.")
    parser.add_argument("--interval", type=float, default=0.2, help="Seconds between repeated captures.")
    parser.add_argument("--min-area", type=float, default=180.0, help="Minimum contour area for a portal candidate.")
    parser.add_argument("--max-area-ratio", type=float, default=0.10, help="Maximum candidate bbox area ratio of frame.")
    parser.add_argument("--threshold", type=float, default=0.42, help="Minimum candidate score to accept.")
    parser.add_argument("--accept-min-width", type=int, default=80, help="Strict accepted portal minimum bbox width.")
    parser.add_argument("--accept-min-height", type=int, default=80, help="Strict accepted portal minimum bbox height.")
    parser.add_argument("--accept-min-area", type=float, default=5000.0, help="Strict accepted portal minimum contour area.")
    parser.add_argument("--accept-min-circularity", type=float, default=0.45, help="Strict accepted portal minimum circularity.")
    parser.add_argument("--accept-min-glow", type=float, default=0.30, help="Strict accepted portal minimum glow fill ratio.")
    parser.add_argument("--accept-max-aspect-skew", type=float, default=1.65, help="Strict accepted portal max width/height skew.")
    parser.add_argument("--top-k", type=int, default=8, help="Maximum number of candidates to print.")
    return parser.parse_args()


def apply_params_file(args: argparse.Namespace) -> argparse.Namespace:
    if not args.params:
        return args
    params_path = Path(args.params)
    if not params_path.is_absolute():
        params_path = ROOT / params_path
    with params_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    allowed_keys = {
        "min_area",
        "max_area_ratio",
        "threshold",
        "accept_min_width",
        "accept_min_height",
        "accept_min_area",
        "accept_min_circularity",
        "accept_min_glow",
        "accept_max_aspect_skew",
        "top_k",
    }
    for key, value in data.items():
        if key in allowed_keys:
            setattr(args, key, value)
    args.params = str(params_path)
    return args


def parse_rect(raw: str) -> dict[str, int]:
    parts = [int(float(part.strip())) for part in raw.split(",") if part.strip()]
    if len(parts) != 4:
        raise ValueError("--rect must be left,top,width,height")
    left, top, width, height = parts
    if width <= 0 or height <= 0:
        raise ValueError("--rect width/height must be positive")
    return {"left": left, "top": top, "width": width, "height": height}


def draw_candidates(frame, candidates: list[PortalMainViewCandidate], args: argparse.Namespace) -> np.ndarray:
    debug = frame.copy()
    params = args_to_params(args)
    for index, candidate in enumerate(candidates, start=1):
        x, y, w, h = candidate.bbox
        color = (0, 255, 0) if is_strict_portal_candidate(candidate, params) else (0, 180, 255)
        cv2.rectangle(debug, (x, y), (x + w, y + h), color, 2)
        cv2.circle(debug, candidate.center, 4, color, -1)
        cv2.putText(
            debug,
            f"{index}:{candidate.score:.2f}",
            (x, max(16, y - 5)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            color,
            2,
            cv2.LINE_AA,
        )
    return debug


def save_image(path: Path, image) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), image)


def print_candidate(prefix: str, candidate: PortalMainViewCandidate, rect: dict[str, int]) -> None:
    sx = rect["left"] + candidate.center[0]
    sy = rect["top"] + candidate.center[1]
    print(
        f"{prefix} "
        f"score={candidate.score:.4f} center={candidate.center} screen_center=({sx}, {sy}) "
        f"bbox={candidate.bbox} area={candidate.area:.1f} glow={candidate.glow_ratio:.3f} "
        f"circularity={candidate.circularity:.3f} aspect={candidate.aspect:.3f}"
    )


def args_to_params(args: argparse.Namespace) -> dict:
    return {
        "threshold": args.threshold,
        "accept_min_width": args.accept_min_width,
        "accept_min_height": args.accept_min_height,
        "accept_min_area": args.accept_min_area,
        "accept_min_circularity": args.accept_min_circularity,
        "accept_min_glow": args.accept_min_glow,
        "accept_max_aspect_skew": args.accept_max_aspect_skew,
    }


def main() -> int:
    dpi_result = set_process_dpi_awareness()
    args = apply_params_file(parse_args())

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    window_info = None
    if args.rect:
        rect = parse_rect(args.rect)
        source = "explicit-rect"
    elif args.full_screen:
        rect = primary_screen_rect()
        source = "primary-screen"
    else:
        window_info = find_game_window(args.window_title, args.window_class)
        if not window_info:
            print("[probe] game window not found; use --rect left,top,width,height or --full-screen")
            return 2
        rect = window_info.rect
        source = "game-window"

    print(f"[probe] dpi={dpi_result}")
    print(f"[probe] source={source} rect={rect}")
    if window_info:
        print(
            "[probe] window "
            f"hwnd={window_info.hwnd} class={window_info.class_name!r} title={window_info.title!r}"
        )

    metadata_path = output_dir / "last_probe_source.json"
    metadata_path.write_text(
        json.dumps(
            {
                "dpi": dpi_result,
                "source": source,
                "rect": rect,
                "window": window_info.__dict__ if window_info else None,
                "threshold": args.threshold,
                "params": args.params,
                "min_area": args.min_area,
                "max_area_ratio": args.max_area_ratio,
                "accept_min_width": args.accept_min_width,
                "accept_min_height": args.accept_min_height,
                "accept_min_area": args.accept_min_area,
                "accept_min_circularity": args.accept_min_circularity,
                "accept_min_glow": args.accept_min_glow,
                "accept_max_aspect_skew": args.accept_max_aspect_skew,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    capture = SquareScreenCapture()
    try:
        for index in range(max(1, int(args.repeat))):
            frame = capture.capture(rect["left"], rect["top"], rect["width"], rect["height"])
            stamp = time.strftime("%Y%m%d_%H%M%S")
            suffix = f"{stamp}_{index + 1:02d}"
            raw_path = output_dir / f"screen_raw_{suffix}.png"
            save_image(raw_path, frame)
            print(f"[probe] saved raw={raw_path}")

            if not args.save_frame_only:
                candidates, mask = detect_portal_candidates(frame, args.min_area, args.max_area_ratio)
                candidates = candidates[: max(1, int(args.top_k))]
                mask_path = output_dir / f"screen_mask_{suffix}.png"
                debug_path = output_dir / f"screen_portal_candidates_{suffix}.png"
                save_image(mask_path, mask)
                save_image(debug_path, draw_candidates(frame, candidates, args))
                print(f"[probe] saved mask={mask_path}")
                print(f"[probe] saved debug={debug_path}")

                params = args_to_params(args)
                accepted = [candidate for candidate in candidates if is_strict_portal_candidate(candidate, params)]
                if accepted:
                    print_candidate("[probe] best", accepted[0], rect)
                    for candidate in accepted:
                        print_candidate("[probe] accepted", candidate, rect)
                else:
                    print(f"[probe] no accepted candidate above threshold={args.threshold:.2f}")
                for candidate in candidates:
                    state = "accepted" if is_strict_portal_candidate(candidate, params) else "below-threshold"
                    print_candidate(f"[probe] candidate {state}", candidate, rect)

            if index + 1 < max(1, int(args.repeat)):
                time.sleep(max(0.0, float(args.interval)))
    finally:
        capture.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
