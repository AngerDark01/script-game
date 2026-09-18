from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass
class TemplateSpec:
    name: str
    path: Path
    image: np.ndarray
    mask: np.ndarray | None = None


@dataclass
class TemplateMatchHit:
    score: float
    gray_score: float
    edge_score: float
    scale: float
    top_left: tuple[int, int]
    size: tuple[int, int]
    template_name: str = ""

    @property
    def center(self) -> tuple[int, int]:
        return (
            int(self.top_left[0] + self.size[0] / 2),
            int(self.top_left[1] + self.size[1] / 2),
        )


def load_template(path: Path) -> TemplateSpec:
    template = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if template is None:
        raise FileNotFoundError(f"template not readable: {path}")
    mask = None
    if template.ndim == 2:
        image = cv2.cvtColor(template, cv2.COLOR_GRAY2BGR)
    elif template.shape[2] == 4:
        image = template[:, :, :3]
        alpha = template[:, :, 3]
        mask = np.where(alpha > 8, 255, 0).astype(np.uint8)
    else:
        image = template[:, :, :3]
    return TemplateSpec(name=path.stem, path=path, image=image, mask=mask)


def match_templates(frame: np.ndarray, templates: list[TemplateSpec], scales: list[float], top_k: int, threshold: float) -> list[TemplateMatchHit]:
    hits: list[TemplateMatchHit] = []
    for template in templates:
        template_hits = match_single_template(frame, template, scales, top_k, threshold)
        hits.extend(template_hits)
    return merge_hits(hits, top_k)


def match_single_template(frame: np.ndarray, template: TemplateSpec, scales: list[float], top_k: int, threshold: float) -> list[TemplateMatchHit]:
    frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    frame_edges = cv2.Canny(frame_gray, 50, 150)
    all_hits: list[TemplateMatchHit] = []

    for scale in scales:
        templ, templ_mask = _resize_template(template.image, template.mask, scale)
        th, tw = templ.shape[:2]
        if th >= frame.shape[0] or tw >= frame.shape[1]:
            continue

        templ_gray = cv2.cvtColor(templ, cv2.COLOR_BGR2GRAY)
        gray_response = cv2.matchTemplate(frame_gray, templ_gray, cv2.TM_CCOEFF_NORMED)
        templ_edges = cv2.Canny(templ_gray, 50, 150)
        if int(np.count_nonzero(templ_edges)) > 4:
            edge_response = cv2.matchTemplate(frame_edges, templ_edges, cv2.TM_CCOEFF_NORMED)
            combined = gray_response * 0.72 + edge_response * 0.28
        else:
            edge_response = np.zeros_like(gray_response)
            combined = gray_response

        if templ_mask is not None and int(np.count_nonzero(templ_mask)) > 8:
            try:
                masked_response = cv2.matchTemplate(frame, templ, cv2.TM_CCORR_NORMED, mask=templ_mask)
                combined = np.maximum(combined, masked_response * 0.82 + gray_response * 0.18)
            except cv2.error:
                pass

        suppress = max(4, min(tw, th) // 2)
        for score, top_left in _response_hits(combined, top_k, threshold, suppress):
            x, y = top_left
            all_hits.append(
                TemplateMatchHit(
                    score=score,
                    gray_score=float(gray_response[y, x]),
                    edge_score=float(edge_response[y, x]),
                    scale=float(scale),
                    top_left=(int(x), int(y)),
                    size=(int(tw), int(th)),
                    template_name=template.name,
                )
            )

    all_hits.sort(key=lambda hit: hit.score, reverse=True)
    return all_hits[:top_k]


def merge_hits(hits: list[TemplateMatchHit], top_k: int, center_radius: float = 12.0) -> list[TemplateMatchHit]:
    selected: list[TemplateMatchHit] = []
    for hit in sorted(hits, key=lambda item: item.score, reverse=True):
        cx, cy = hit.center
        duplicate = False
        for kept in selected:
            kx, ky = kept.center
            radius = max(center_radius, min(hit.size + kept.size) * 0.35)
            if float(np.hypot(cx - kx, cy - ky)) <= radius:
                duplicate = True
                break
        if not duplicate:
            selected.append(hit)
        if len(selected) >= top_k:
            break
    return selected


def _resize_template(template: np.ndarray, mask: np.ndarray | None, scale: float):
    h, w = template.shape[:2]
    new_w = max(4, int(round(w * scale)))
    new_h = max(4, int(round(h * scale)))
    resized = cv2.resize(template, (new_w, new_h), interpolation=cv2.INTER_AREA)
    resized_mask = None
    if mask is not None:
        resized_mask = cv2.resize(mask, (new_w, new_h), interpolation=cv2.INTER_NEAREST)
    return resized, resized_mask


def _response_hits(response: np.ndarray, limit: int, threshold: float, suppress_radius: int):
    hits = []
    work = response.copy()
    for _ in range(limit):
        _, max_val, _, max_loc = cv2.minMaxLoc(work)
        if max_val < threshold:
            break
        hits.append((float(max_val), max_loc))
        x, y = max_loc
        x1 = max(0, x - suppress_radius)
        y1 = max(0, y - suppress_radius)
        x2 = min(work.shape[1], x + suppress_radius + 1)
        y2 = min(work.shape[0], y + suppress_radius + 1)
        work[y1:y2, x1:x2] = -1.0
    return hits

