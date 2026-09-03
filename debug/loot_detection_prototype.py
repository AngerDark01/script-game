from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
from pathlib import Path

import cv2
import numpy as np


@dataclass
class LootTemplate:
    name: str
    image: np.ndarray
    mask: np.ndarray


@dataclass
class LootCandidate:
    score: float
    template_score: float
    shape_score: float
    color_score: float
    scale: float
    top_left: tuple[int, int]
    size: tuple[int, int]
    center: tuple[int, int]
    template_name: str
    color_pixels: int
    accepted: bool


@dataclass
class LootCluster:
    score: float
    center: tuple[int, int]
    bbox: tuple[int, int, int, int]
    candidates: int
    templates: list[str]


def main() -> None:
    args = parse_args()
    template_dir = Path(args.templates) if args.templates else default_template_dir()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    templates = load_templates(template_dir)
    if not templates:
        raise SystemExit(f"no loot templates found: {template_dir}")

    if args.image:
        frame = read_image(Path(args.image))
        input_path = Path(args.image)
    else:
        frame = synthesize_probe_frame(templates)
        input_path = out_dir / "synthetic_loot_input.png"
        write_image(input_path, frame)

    frame = pad_small_frame(frame, templates)
    candidates = detect_loot_candidates(
        frame,
        templates,
        scales=parse_scales(args.scales),
        top_k=int(args.top_k),
        collect_threshold=float(args.collect_threshold),
        accept_threshold=float(args.threshold),
    )
    accepted = [candidate for candidate in candidates if candidate.accepted]
    clusters = cluster_candidates(accepted)

    overlay = draw_overlay(frame.copy(), candidates, clusters)
    overlay_path = out_dir / "loot_detection_overlay.png"
    write_image(overlay_path, overlay)

    result = {
        "input": str(input_path),
        "templates": [template.name for template in templates],
        "candidate_count": len(candidates),
        "accepted_count": len(accepted),
        "cluster_count": len(clusters),
        "accepted_candidates": [asdict(candidate) for candidate in accepted[:20]],
        "clusters": [asdict(cluster) for cluster in clusters],
        "overlay": str(overlay_path),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PROTOTYPE: weighted minimap loot detector probe.")
    parser.add_argument("--image", default="", help="Optional minimap image. If omitted, a synthetic stacked frame is generated.")
    parser.add_argument("--templates", default="", help="Loot template directory. Defaults to D:/ACloud/image/<first subdir>.")
    parser.add_argument("--out-dir", default="debug/loot_detection_probe", help="Output directory for prototype artifacts.")
    parser.add_argument("--threshold", type=float, default=0.54, help="Final weighted score threshold.")
    parser.add_argument("--collect-threshold", type=float, default=0.28, help="Loose template/edge response threshold for candidate collection.")
    parser.add_argument("--top-k", type=int, default=24, help="Maximum raw hits per template before clustering.")
    parser.add_argument("--scales", default="0.75,0.85,1.0,1.15,1.3", help="Comma-separated template scales.")
    return parser.parse_args()


def default_template_dir() -> Path:
    cloud_root = Path(__file__).resolve().parents[2]
    image_root = cloud_root / "image"
    if not image_root.exists():
        return image_root
    dirs = [path for path in image_root.iterdir() if path.is_dir()]
    return dirs[0] if dirs else image_root


def parse_scales(raw: str) -> list[float]:
    return [float(item.strip()) for item in raw.split(",") if item.strip()]


def read_image(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise FileNotFoundError(f"image not readable: {path}")
    return to_bgr(image)


def write_image(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(path.suffix or ".png", image)
    if not ok:
        raise RuntimeError(f"failed to encode image: {path}")
    encoded.tofile(str(path))


def to_bgr(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.shape[2] == 4:
        return image[:, :, :3]
    return image[:, :, :3]


def load_templates(template_dir: Path) -> list[LootTemplate]:
    templates = []
    for path in sorted(template_dir.iterdir(), key=lambda item: item.name):
        if not path.is_file() or path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".bmp"}:
            continue
        image = read_image(path)
        mask = foreground_mask(image)
        if int(np.count_nonzero(mask)) < 20:
            continue
        templates.append(LootTemplate(name=path.stem, image=image, mask=mask))
    return templates


def pad_small_frame(frame: np.ndarray, templates: list[LootTemplate]) -> np.ndarray:
    max_w = max(template.image.shape[1] for template in templates)
    max_h = max(template.image.shape[0] for template in templates)
    h, w = frame.shape[:2]
    pad_x = max(0, max_w + 16 - w)
    pad_y = max(0, max_h + 16 - h)
    if pad_x <= 0 and pad_y <= 0:
        return frame
    left = pad_x // 2 + 12
    right = pad_x - pad_x // 2 + 12
    top = pad_y // 2 + 12
    bottom = pad_y - pad_y // 2 + 12
    return cv2.copyMakeBorder(frame, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(49, 49, 53))


def foreground_mask(image: np.ndarray) -> np.ndarray:
    bgr = to_bgr(image)
    max_channel = np.max(bgr, axis=2)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 40, 120)
    mask = ((max_channel > 42) | (edges > 0)).astype(np.uint8) * 255
    kernel = np.ones((3, 3), np.uint8)
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)


def detect_loot_candidates(
    frame: np.ndarray,
    templates: list[LootTemplate],
    *,
    scales: list[float],
    top_k: int,
    collect_threshold: float,
    accept_threshold: float,
) -> list[LootCandidate]:
    frame = to_bgr(frame)
    frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    frame_edges = cv2.Canny(frame_gray, 45, 135)
    candidates: list[LootCandidate] = []

    for template in templates:
        for scale in scales:
            templ, templ_mask = resize_template(template.image, template.mask, scale)
            th, tw = templ.shape[:2]
            if th >= frame.shape[0] or tw >= frame.shape[1]:
                continue

            templ_gray = cv2.cvtColor(templ, cv2.COLOR_BGR2GRAY)
            templ_edges = cv2.Canny(templ_gray, 45, 135)
            gray_response = cv2.matchTemplate(frame_gray, templ_gray, cv2.TM_CCOEFF_NORMED)
            edge_response = np.zeros_like(gray_response)
            if int(np.count_nonzero(templ_edges)) > 6:
                edge_response = cv2.matchTemplate(frame_edges, templ_edges, cv2.TM_CCOEFF_NORMED)

            response = np.maximum(gray_response, edge_response * 0.9)
            if int(np.count_nonzero(templ_mask)) > 20:
                try:
                    masked_response = cv2.matchTemplate(frame, templ, cv2.TM_CCORR_NORMED, mask=templ_mask)
                    response = np.maximum(response, masked_response * 0.92)
                except cv2.error:
                    pass

            suppress = max(6, min(tw, th) // 2)
            for _, top_left in response_hits(response, top_k, collect_threshold, suppress):
                x, y = top_left
                patch = frame[y:y + th, x:x + tw]
                template_score = clamp01(float(response[y, x]))
                shape_score = clamp01(float(edge_response[y, x]))
                color_score, color_pixels = loot_color_score(patch)
                score = weighted_score(template_score, shape_score, color_score)
                accepted = bool(
                    score >= accept_threshold
                    and color_score >= 0.12
                    and (template_score >= 0.25 or shape_score >= 0.22)
                )
                candidates.append(
                    LootCandidate(
                        score=float(score),
                        template_score=float(template_score),
                        shape_score=float(shape_score),
                        color_score=float(color_score),
                        scale=float(scale),
                        top_left=(int(x), int(y)),
                        size=(int(tw), int(th)),
                        center=(int(x + tw / 2), int(y + th / 2)),
                        template_name=template.name,
                        color_pixels=int(color_pixels),
                        accepted=accepted,
                    )
                )

    candidates.sort(key=lambda item: item.score, reverse=True)
    return merge_duplicate_candidates(candidates, top_k * max(1, len(templates)))


def resize_template(image: np.ndarray, mask: np.ndarray, scale: float) -> tuple[np.ndarray, np.ndarray]:
    h, w = image.shape[:2]
    new_w = max(4, int(round(w * scale)))
    new_h = max(4, int(round(h * scale)))
    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
    resized_mask = cv2.resize(mask, (new_w, new_h), interpolation=cv2.INTER_NEAREST)
    return resized, resized_mask


def response_hits(response: np.ndarray, limit: int, threshold: float, suppress_radius: int):
    hits = []
    work = response.copy()
    for _ in range(max(1, int(limit))):
        _, max_val, _, max_loc = cv2.minMaxLoc(work)
        if float(max_val) < float(threshold):
            break
        hits.append((float(max_val), max_loc))
        x, y = max_loc
        x1 = max(0, x - suppress_radius)
        y1 = max(0, y - suppress_radius)
        x2 = min(work.shape[1], x + suppress_radius + 1)
        y2 = min(work.shape[0], y + suppress_radius + 1)
        work[y1:y2, x1:x2] = -1.0
    return hits


def loot_color_score(patch: np.ndarray) -> tuple[float, int]:
    if patch.size == 0:
        return 0.0, 0
    hsv = cv2.cvtColor(to_bgr(patch), cv2.COLOR_BGR2HSV)
    h = hsv[:, :, 0]
    s = hsv[:, :, 1]
    v = hsv[:, :, 2]
    gold = (h >= 14) & (h <= 45) & (s >= 55) & (v >= 95)
    warm = ((h <= 18) | (h >= 170)) & (s >= 35) & (v >= 70)
    silver = (s <= 55) & (v >= 135)
    bright = v >= 165
    mask = gold | warm | silver | bright
    pixels = int(np.count_nonzero(mask))
    area = int(patch.shape[0] * patch.shape[1])
    ratio = float(pixels / max(1, area))
    ratio_score = min(1.0, ratio / 0.18)
    pixel_score = min(1.0, pixels / 90.0)
    return float(ratio_score * 0.72 + pixel_score * 0.28), pixels


def weighted_score(template_score: float, shape_score: float, color_score: float) -> float:
    return (
        clamp01(template_score) * 0.40
        + clamp01(shape_score) * 0.34
        + clamp01(color_score) * 0.26
    )


def merge_duplicate_candidates(candidates: list[LootCandidate], limit: int) -> list[LootCandidate]:
    selected: list[LootCandidate] = []
    for candidate in candidates:
        duplicate = False
        for kept in selected:
            if center_distance(candidate.center, kept.center) <= max(8.0, min(candidate.size + kept.size) * 0.28):
                duplicate = True
                break
        if not duplicate:
            selected.append(candidate)
        if len(selected) >= int(limit):
            break
    return selected


def cluster_candidates(candidates: list[LootCandidate]) -> list[LootCluster]:
    clusters: list[list[LootCandidate]] = []
    for candidate in sorted(candidates, key=lambda item: item.score, reverse=True):
        target_cluster = None
        for cluster in clusters:
            if any(should_cluster(candidate, kept) for kept in cluster):
                target_cluster = cluster
                break
        if target_cluster is None:
            clusters.append([candidate])
        else:
            target_cluster.append(candidate)

    result = []
    for cluster in clusters:
        xs = [item.top_left[0] for item in cluster]
        ys = [item.top_left[1] for item in cluster]
        rights = [item.top_left[0] + item.size[0] for item in cluster]
        bottoms = [item.top_left[1] + item.size[1] for item in cluster]
        weights = np.array([max(0.01, item.score) for item in cluster], dtype=np.float32)
        centers = np.array([item.center for item in cluster], dtype=np.float32)
        center = np.average(centers, axis=0, weights=weights)
        result.append(
            LootCluster(
                score=float(max(item.score for item in cluster)),
                center=(int(round(center[0])), int(round(center[1]))),
                bbox=(int(min(xs)), int(min(ys)), int(max(rights) - min(xs)), int(max(bottoms) - min(ys))),
                candidates=len(cluster),
                templates=sorted({item.template_name for item in cluster}),
            )
        )
    result.sort(key=lambda item: item.score, reverse=True)
    return merge_overlapping_clusters(result)


def merge_overlapping_clusters(clusters: list[LootCluster]) -> list[LootCluster]:
    merged: list[LootCluster] = []
    for cluster in clusters:
        target_index = None
        for index, kept in enumerate(merged):
            if clusters_overlap(cluster, kept):
                target_index = index
                break
        if target_index is None:
            merged.append(cluster)
        else:
            merged[target_index] = merge_two_clusters(merged[target_index], cluster)
    merged.sort(key=lambda item: item.score, reverse=True)
    return merged


def clusters_overlap(a: LootCluster, b: LootCluster) -> bool:
    if bbox_iou((a.bbox[0], a.bbox[1]), (a.bbox[2], a.bbox[3]), (b.bbox[0], b.bbox[1]), (b.bbox[2], b.bbox[3])) > 0.02:
        return True
    return point_in_bbox(a.center, b.bbox) or point_in_bbox(b.center, a.bbox)


def merge_two_clusters(a: LootCluster, b: LootCluster) -> LootCluster:
    ax, ay, aw, ah = a.bbox
    bx, by, bw, bh = b.bbox
    x1 = min(ax, bx)
    y1 = min(ay, by)
    x2 = max(ax + aw, bx + bw)
    y2 = max(ay + ah, by + bh)
    total = max(1, a.candidates + b.candidates)
    center = (
        int(round((a.center[0] * a.candidates + b.center[0] * b.candidates) / total)),
        int(round((a.center[1] * a.candidates + b.center[1] * b.candidates) / total)),
    )
    return LootCluster(
        score=max(float(a.score), float(b.score)),
        center=center,
        bbox=(int(x1), int(y1), int(x2 - x1), int(y2 - y1)),
        candidates=total,
        templates=sorted(set(a.templates + b.templates)),
    )


def point_in_bbox(point: tuple[int, int], bbox: tuple[int, int, int, int]) -> bool:
    x, y = point
    left, top, width, height = bbox
    return left <= x <= left + width and top <= y <= top + height


def should_cluster(a: LootCandidate, b: LootCandidate) -> bool:
    if bbox_iou(a.top_left, a.size, b.top_left, b.size) > 0.08:
        return True
    radius = max(a.size[0], a.size[1], b.size[0], b.size[1]) * 0.58
    return center_distance(a.center, b.center) <= radius


def bbox_iou(a_top_left, a_size, b_top_left, b_size) -> float:
    ax1, ay1 = a_top_left
    aw, ah = a_size
    bx1, by1 = b_top_left
    bw, bh = b_size
    ax2, ay2 = ax1 + aw, ay1 + ah
    bx2, by2 = bx1 + bw, by1 + bh
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    union = aw * ah + bw * bh - inter
    return float(inter / max(1, union))


def center_distance(a: tuple[int, int], b: tuple[int, int]) -> float:
    return float(np.hypot(float(a[0] - b[0]), float(a[1] - b[1])))


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def synthesize_probe_frame(templates: list[LootTemplate]) -> np.ndarray:
    frame = np.full((260, 360, 3), (49, 49, 53), dtype=np.uint8)
    cv2.line(frame, (20, 40), (340, 42), (82, 82, 87), 2)
    cv2.line(frame, (60, 210), (310, 175), (34, 34, 38), 4)
    cv2.circle(frame, (268, 82), 18, (92, 86, 74), 2)

    placements = [
        (templates[0], 142, 82, 1.0),
        (templates[min(1, len(templates) - 1)], 168, 98, 1.0),
        (templates[min(2, len(templates) - 1)], 151, 123, 1.05),
        (templates[-1], 215, 158, 0.9),
    ]
    for template, x, y, scale in placements:
        image, mask = resize_template(template.image, template.mask, scale)
        paste_foreground(frame, image, mask, x, y)
    return frame


def paste_foreground(frame: np.ndarray, image: np.ndarray, mask: np.ndarray, x: int, y: int) -> None:
    h, w = image.shape[:2]
    left = max(0, int(x))
    top = max(0, int(y))
    right = min(frame.shape[1], left + w)
    bottom = min(frame.shape[0], top + h)
    if right <= left or bottom <= top:
        return
    crop = image[: bottom - top, : right - left]
    crop_mask = mask[: bottom - top, : right - left] > 0
    roi = frame[top:bottom, left:right]
    roi[crop_mask] = crop[crop_mask]


def draw_overlay(frame: np.ndarray, candidates: list[LootCandidate], clusters: list[LootCluster]) -> np.ndarray:
    for candidate in candidates[:60]:
        color = (0, 180, 0) if candidate.accepted else (80, 80, 80)
        x, y = candidate.top_left
        w, h = candidate.size
        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 1)
        if candidate.accepted:
            cv2.putText(
                frame,
                f"{candidate.score:.2f}",
                (x, max(10, y - 3)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.35,
                color,
                1,
                cv2.LINE_AA,
            )
    for cluster in clusters:
        x, y, w, h = cluster.bbox
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
        cv2.circle(frame, cluster.center, 4, (0, 0, 255), -1)
        cv2.putText(
            frame,
            f"loot {cluster.score:.2f} n={cluster.candidates}",
            (x, min(frame.shape[0] - 5, y + h + 14)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            (0, 0, 255),
            1,
            cv2.LINE_AA,
        )
    return frame


if __name__ == "__main__":
    main()
