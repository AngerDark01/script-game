from __future__ import annotations

import numpy as np

from .models import LootCandidate, LootCluster


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
                template_score=float(max(item.template_score for item in cluster)),
                shape_score=float(max(item.shape_score for item in cluster)),
                color_score=float(max(item.color_score for item in cluster)),
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
        template_score=max(float(a.template_score), float(b.template_score)),
        shape_score=max(float(a.shape_score), float(b.shape_score)),
        color_score=max(float(a.color_score), float(b.color_score)),
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

