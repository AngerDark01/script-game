from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.localization import NavigationCore
from core.localization.frame_matcher import scale_wall_template, select_template_search_area
from gui.navigation_params import NavConfig


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe first-frame navigation localization with production NavigationCore settings.",
    )
    parser.add_argument("--map-folder", default=str(PROJECT_ROOT / "map_data" / "A"))
    parser.add_argument("--image", required=True)
    parser.add_argument("--out", default="")
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--expected", default="", help="Optional expected global coordinate as x,y.")
    parser.add_argument("--player", default="", help="Optional player local coordinate as x,y.")
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except UnicodeError:
        return json.loads(path.read_text(encoding="utf-8"))


def parse_point(text: str) -> tuple[float, float] | None:
    if not text:
        return None
    parts = [part.strip() for part in text.split(",")]
    if len(parts) != 2:
        raise ValueError(f"Expected x,y point, got: {text!r}")
    return (float(parts[0]), float(parts[1]))


def json_ready(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, tuple):
        return [json_ready(item) for item in value]
    if isinstance(value, list):
        return [json_ready(item) for item in value]
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    return value


def load_npz_summary(map_folder: Path) -> dict[str, Any]:
    path = map_folder / "map_data.npz"
    data = np.load(path)
    summary: dict[str, Any] = {
        "path": str(path),
        "keys": sorted(str(key) for key in data.files),
        "canvas_size": int(data["canvas_size"]) if "canvas_size" in data else None,
        "draw_scale": float(data["draw_scale"]) if "draw_scale" in data else None,
        "wall_close_kernel_size": int(data["wall_close_kernel_size"]) if "wall_close_kernel_size" in data else None,
        "current_pos": None,
    }
    if "current_pos" in data:
        pos = data["current_pos"]
        summary["current_pos"] = [float(pos[0]), float(pos[1])]
    return summary


def apply_localization_config(nav_core: NavigationCore, nav_config: NavConfig) -> dict[str, Any]:
    nav_core.recognizer.set_params(nav_config.recognizer_params.__dict__)
    map_draw_scale = float(getattr(nav_core, "map_draw_scale", nav_core.draw_scale))
    config_draw_scale = float(getattr(nav_config, "draw_scale", map_draw_scale))
    nav_core.draw_scale = map_draw_scale
    nav_core.wall_match_close_kernel_size = max(
        1,
        int(
            getattr(
                nav_core,
                "map_wall_match_close_kernel_size",
                getattr(nav_config, "wall_match_close_kernel_size", 3),
            )
        ),
    )
    nav_core.visual_check_interval_ms = max(0, int(nav_config.coordinate_visual_check_interval_ms))
    nav_core.visual_check_margin = max(0, int(nav_config.coordinate_visual_check_margin))
    nav_core.visual_check_min_confidence = max(
        0.0,
        min(0.99, float(nav_config.coordinate_visual_match_min_confidence)),
    )
    nav_core.visual_mismatch_threshold = max(0.0, float(nav_config.coordinate_visual_mismatch_threshold))
    return {
        "config_draw_scale": config_draw_scale,
        "map_draw_scale": map_draw_scale,
        "used_draw_scale": float(nav_core.draw_scale),
        "draw_scale_mismatch": abs(config_draw_scale - map_draw_scale) > 0.001,
        "wall_match_close_kernel_size": int(nav_core.wall_match_close_kernel_size),
        "visual_check_interval_ms": int(nav_core.visual_check_interval_ms),
        "visual_check_margin": int(nav_core.visual_check_margin),
        "visual_check_min_confidence": float(nav_core.visual_check_min_confidence),
        "visual_mismatch_threshold": float(nav_core.visual_mismatch_threshold),
    }


def resolve_player_pos(args: argparse.Namespace, metadata: dict[str, Any], image: np.ndarray) -> tuple[int, int]:
    explicit = parse_point(args.player)
    if explicit is not None:
        return (int(round(explicit[0])), int(round(explicit[1])))
    meta_player = metadata.get("player_local_pos")
    if meta_player and len(meta_player) >= 2:
        return (int(round(float(meta_player[0]))), int(round(float(meta_player[1]))))
    h_img, w_img = image.shape[:2]
    return (w_img // 2, h_img // 2)


def extract_masks(nav_core: NavigationCore, image: np.ndarray, player_pos: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:
    masks = nav_core.recognizer.extract_combined(image, player_pos=player_pos)
    if masks is None:
        raise RuntimeError("Recognizer returned no localization masks.")
    if isinstance(masks, tuple) and len(masks) >= 2:
        return masks[0], masks[1]
    return masks[0], masks[0]


def compute_template_result(
    nav_core: NavigationCore,
    wall_mask: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, tuple[int, int], np.ndarray]:
    search_area, top_left_offset = select_template_search_area(
        wall_layer=nav_core.wall_layer,
        current_pos=nav_core.current_pos,
        canvas_size=nav_core.canvas_size,
        local_search_radius=nav_core.local_search_radius,
        full_map_localization=True,
        wall_mask_shape=wall_mask.shape,
        draw_scale=nav_core.draw_scale,
    )
    wall_mask_scaled = scale_wall_template(
        wall_mask,
        nav_core.draw_scale,
        getattr(nav_core, "wall_match_close_kernel_size", 3),
    )
    if search_area.dtype != np.uint8:
        search_area = search_area.astype(np.uint8)
    if wall_mask_scaled.dtype != np.uint8:
        wall_mask_scaled = wall_mask_scaled.astype(np.uint8)
    result = cv2.matchTemplate(search_area, wall_mask_scaled, cv2.TM_CCOEFF_NORMED)
    return search_area, wall_mask_scaled, top_left_offset, result


def top_candidates(
    result: np.ndarray,
    *,
    top_left_offset: tuple[int, int],
    player_pos: tuple[int, int],
    draw_scale: float,
    template_shape: tuple[int, int],
    max_count: int,
) -> list[dict[str, Any]]:
    work = result.copy()
    candidates: list[dict[str, Any]] = []
    h_t, w_t = template_shape[:2]
    player_scaled = (int(player_pos[0] * draw_scale), int(player_pos[1] * draw_scale))
    suppress_radius = max(24, min(h_t, w_t) // 4)
    for _ in range(max(1, max_count) * 8):
        _, max_val, _, max_loc = cv2.minMaxLoc(work)
        if not np.isfinite(max_val) or max_val <= -1.0:
            break
        top_left = (int(top_left_offset[0] + max_loc[0]), int(top_left_offset[1] + max_loc[1]))
        center = (int(top_left[0] + player_scaled[0]), int(top_left[1] + player_scaled[1]))
        if all(np.hypot(center[0] - old["center"][0], center[1] - old["center"][1]) >= suppress_radius for old in candidates):
            candidates.append(
                {
                    "rank": len(candidates) + 1,
                    "score": float(max_val),
                    "center": [center[0], center[1]],
                    "template_top_left": [top_left[0], top_left[1]],
                }
            )
            if len(candidates) >= max_count:
                break
        x0 = max(0, int(max_loc[0] - suppress_radius))
        y0 = max(0, int(max_loc[1] - suppress_radius))
        x1 = min(work.shape[1], int(max_loc[0] + suppress_radius + 1))
        y1 = min(work.shape[0], int(max_loc[1] + suppress_radius + 1))
        work[y0:y1, x0:x1] = -1.0
    return candidates


def score_at_center(
    result: np.ndarray,
    *,
    center: tuple[float, float] | None,
    player_pos: tuple[int, int],
    draw_scale: float,
) -> float | None:
    if center is None:
        return None
    player_scaled = (int(player_pos[0] * draw_scale), int(player_pos[1] * draw_scale))
    x = int(round(center[0] - player_scaled[0]))
    y = int(round(center[1] - player_scaled[1]))
    if y < 0 or x < 0 or y >= result.shape[0] or x >= result.shape[1]:
        return None
    return float(result[y, x])


def to_bgr(image: np.ndarray) -> np.ndarray:
    if len(image.shape) == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    return image.copy()


def crop_with_padding(image: np.ndarray, top_left: tuple[int, int], size: tuple[int, int]) -> np.ndarray:
    h, w = size
    x, y = top_left
    if len(image.shape) == 2:
        out = np.zeros((h, w), dtype=image.dtype)
    else:
        out = np.zeros((h, w, image.shape[2]), dtype=image.dtype)
    src_x0 = max(0, x)
    src_y0 = max(0, y)
    src_x1 = min(image.shape[1], x + w)
    src_y1 = min(image.shape[0], y + h)
    if src_x1 <= src_x0 or src_y1 <= src_y0:
        return out
    dst_x0 = src_x0 - x
    dst_y0 = src_y0 - y
    out[dst_y0 : dst_y0 + (src_y1 - src_y0), dst_x0 : dst_x0 + (src_x1 - src_x0)] = image[src_y0:src_y1, src_x0:src_x1]
    return out


def save_center_patch(
    image: np.ndarray,
    out_path: Path,
    *,
    center: tuple[float, float] | None,
    player_pos: tuple[int, int],
    draw_scale: float,
    template_shape: tuple[int, int],
) -> tuple[int, int] | None:
    if center is None:
        return None
    player_scaled = (int(player_pos[0] * draw_scale), int(player_pos[1] * draw_scale))
    top_left = (int(round(center[0] - player_scaled[0])), int(round(center[1] - player_scaled[1])))
    patch = crop_with_padding(image, top_left, template_shape[:2])
    cv2.imwrite(str(out_path), patch)
    return top_left


def save_candidate_sheet(
    wall_layer: np.ndarray,
    out_path: Path,
    *,
    candidates: list[dict[str, Any]],
    template_shape: tuple[int, int],
) -> None:
    if not candidates:
        return
    h_t, w_t = template_shape[:2]
    cell_h = min(260, h_t)
    cell_w = min(260, w_t)
    cells: list[np.ndarray] = []
    for candidate in candidates[:6]:
        top_left = tuple(candidate["template_top_left"])
        patch = crop_with_padding(wall_layer, (int(top_left[0]), int(top_left[1])), (h_t, w_t))
        patch = cv2.resize(to_bgr(patch), (cell_w, cell_h), interpolation=cv2.INTER_NEAREST)
        cv2.putText(
            patch,
            f"#{candidate['rank']} {candidate['score']:.3f}",
            (8, 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 255, 255),
            2,
            cv2.LINE_AA,
        )
        cells.append(patch)
    sheet = np.hstack(cells)
    cv2.imwrite(str(out_path), sheet)


def main() -> int:
    args = parse_args()
    map_folder = Path(args.map_folder).resolve()
    image_path = Path(args.image).resolve()
    if not image_path.exists():
        raise FileNotFoundError(image_path)
    metadata = load_json(image_path.with_suffix(".json"))
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"Failed to read image: {image_path}")

    stamp = time.strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.out).resolve() if args.out else PROJECT_ROOT / "debug" / "navigation_localization_probe" / f"{stamp}_{image_path.stem}"
    out_dir.mkdir(parents=True, exist_ok=True)

    config_data = load_json(map_folder / "config.json")
    nav_config = NavConfig.from_dict(config_data)
    npz_summary = load_npz_summary(map_folder)
    nav_core = NavigationCore(str(map_folder))
    applied_config = apply_localization_config(nav_core, nav_config)

    player_pos = resolve_player_pos(args, metadata, image)
    expected = parse_point(args.expected)
    saved_pos = None
    if npz_summary.get("current_pos"):
        saved_pos = (float(npz_summary["current_pos"][0]), float(npz_summary["current_pos"][1]))

    match_mask, wall_mask = extract_masks(nav_core, image, player_pos)
    search_area, wall_mask_scaled, top_left_offset, result = compute_template_result(nav_core, wall_mask)
    candidates = top_candidates(
        result,
        top_left_offset=top_left_offset,
        player_pos=player_pos,
        draw_scale=nav_core.draw_scale,
        template_shape=wall_mask_scaled.shape,
        max_count=int(args.top),
    )

    x, y, confidence = nav_core.localize(image, player_pos=player_pos)
    registration = nav_core.last_frame_registration
    result_pos = None if x is None or y is None else (float(x), float(y))
    top_candidate = candidates[0] if candidates else None

    cv2.imwrite(str(out_dir / "input_minimap.png"), image)
    if image_path.with_suffix(".json").exists():
        shutil.copy2(image_path.with_suffix(".json"), out_dir / "input_minimap.json")
    cv2.imwrite(str(out_dir / "match_mask.png"), match_mask)
    cv2.imwrite(str(out_dir / "wall_mask.png"), wall_mask)
    cv2.imwrite(str(out_dir / "wall_mask_scaled.png"), wall_mask_scaled)
    if top_candidate is not None:
        crop_top_left = tuple(top_candidate["template_top_left"])
        cv2.imwrite(
            str(out_dir / "matched_map_patch.png"),
            crop_with_padding(nav_core.wall_layer, (int(crop_top_left[0]), int(crop_top_left[1])), wall_mask_scaled.shape[:2]),
        )
    saved_top_left = save_center_patch(
        nav_core.wall_layer,
        out_dir / "saved_pos_patch.png",
        center=saved_pos,
        player_pos=player_pos,
        draw_scale=nav_core.draw_scale,
        template_shape=wall_mask_scaled.shape,
    )
    expected_top_left = save_center_patch(
        nav_core.wall_layer,
        out_dir / "expected_pos_patch.png",
        center=expected,
        player_pos=player_pos,
        draw_scale=nav_core.draw_scale,
        template_shape=wall_mask_scaled.shape,
    )
    save_candidate_sheet(
        nav_core.wall_layer,
        out_dir / "top_candidates_sheet.png",
        candidates=candidates,
        template_shape=wall_mask_scaled.shape,
    )

    report = {
        "map_folder": str(map_folder),
        "image": str(image_path),
        "out_dir": str(out_dir),
        "metadata": metadata,
        "player_local_pos": [int(player_pos[0]), int(player_pos[1])],
        "config": applied_config,
        "npz": npz_summary,
        "features": {
            "match_feature_count": int(cv2.countNonZero(match_mask)),
            "wall_feature_count": int(cv2.countNonZero(wall_mask)),
            "scaled_template_shape": list(wall_mask_scaled.shape),
            "search_area_shape": list(search_area.shape),
        },
        "localize_result": {
            "position": None if result_pos is None else [result_pos[0], result_pos[1]],
            "confidence": float(confidence or 0.0),
            "registration": {
                "valid": bool(getattr(registration, "valid", False)),
                "source": getattr(registration, "source", ""),
                "confidence": float(getattr(registration, "confidence", 0.0) or 0.0),
                "frame_origin_global": getattr(registration, "frame_origin_global", None),
                "player_global_pos": getattr(registration, "player_global_pos", None),
                "player_local_minimap_pos": getattr(registration, "player_local_minimap_pos", None),
                "metadata": getattr(registration, "metadata", {}) or {},
            },
        },
        "top_candidates": candidates,
        "saved_pos_check": {
            "saved_pos": None if saved_pos is None else [saved_pos[0], saved_pos[1]],
            "template_top_left": None if saved_top_left is None else [int(saved_top_left[0]), int(saved_top_left[1])],
            "score": score_at_center(
                result,
                center=saved_pos,
                player_pos=player_pos,
                draw_scale=nav_core.draw_scale,
            ),
        },
        "expected_check": {
            "expected_pos": None if expected is None else [expected[0], expected[1]],
            "template_top_left": None if expected_top_left is None else [int(expected_top_left[0]), int(expected_top_left[1])],
            "score": score_at_center(
                result,
                center=expected,
                player_pos=player_pos,
                draw_scale=nav_core.draw_scale,
            ),
        },
    }
    (out_dir / "report.json").write_text(
        json.dumps(json_ready(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(json_ready({
        "out_dir": str(out_dir),
        "position": report["localize_result"]["position"],
        "confidence": report["localize_result"]["confidence"],
        "top_candidate": top_candidate,
        "saved_pos_score": report["saved_pos_check"]["score"],
        "expected_score": report["expected_check"]["score"],
    }), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
