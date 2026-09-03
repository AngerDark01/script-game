from __future__ import annotations

import json
from dataclasses import dataclass

import cv2
import numpy as np

from core.events.debug import event_log

from .assets import PORTAL_MAIN_VIEW_PARAMS


@dataclass
class PortalMainViewCandidate:
    score: float
    area: float
    glow_ratio: float
    circularity: float
    aspect: float
    bbox: tuple[int, int, int, int]
    center: tuple[int, int]


class PortalMainViewConfirmer:
    def __init__(self, params_path=PORTAL_MAIN_VIEW_PARAMS):
        self.params = _load_params(params_path)
        self._last_log_ms = 0.0

    def confirm(self, frame) -> list[PortalMainViewCandidate]:
        if frame is None:
            self._log_throttled("portal main-view confirm skipped", frame=False)
            return []
        candidates, _mask = detect_portal_candidates(
            frame,
            min_area=float(self.params.get("min_area", 180.0)),
            max_area_ratio=float(self.params.get("max_area_ratio", 0.10)),
        )
        accepted = [candidate for candidate in candidates if is_strict_portal_candidate(candidate, self.params)]
        if accepted:
            best = accepted[0]
            event_log(
                "portal main-view accepted",
                candidates=len(candidates),
                accepted=len(accepted),
                score=float(best.score),
                center=best.center,
                bbox=best.bbox,
            )
        else:
            best_score = float(candidates[0].score) if candidates else 0.0
            self._log_throttled(
                "portal main-view no accepted",
                candidates=len(candidates),
                best_score=best_score,
            )
        return accepted

    def _log_throttled(self, message: str, **fields) -> None:
        import time

        now_ms = time.monotonic() * 1000.0
        if now_ms - self._last_log_ms < 1000:
            return
        self._last_log_ms = now_ms
        event_log(message, **fields)


def build_blue_glow_mask(frame: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    cyan = cv2.inRange(hsv, np.array([86, 70, 110]), np.array([108, 255, 255]))
    blue = cv2.inRange(hsv, np.array([109, 55, 95]), np.array([132, 255, 255]))
    violet = cv2.inRange(hsv, np.array([133, 45, 90]), np.array([158, 255, 255]))
    mask = cv2.bitwise_or(cv2.bitwise_or(cyan, blue), violet)
    open_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    close_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, open_kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, close_kernel, iterations=2)
    mask = cv2.dilate(mask, open_kernel, iterations=1)
    return mask


def detect_portal_candidates(frame: np.ndarray, min_area: float, max_area_ratio: float) -> tuple[list[PortalMainViewCandidate], np.ndarray]:
    mask = build_blue_glow_mask(frame)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    frame_area = float(frame.shape[0] * frame.shape[1])
    candidates: list[PortalMainViewCandidate] = []
    for contour in contours:
        area = float(cv2.contourArea(contour))
        if area < min_area:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        bbox_area = float(w * h)
        if bbox_area <= 0 or bbox_area / frame_area > max_area_ratio:
            continue
        if w < 12 or h < 12:
            continue
        aspect = float(w / max(1, h))
        if aspect < 0.28 or aspect > 3.2:
            continue
        perimeter = float(cv2.arcLength(contour, True))
        circularity = float(4.0 * np.pi * area / (perimeter * perimeter)) if perimeter > 1 else 0.0
        local_mask = mask[y : y + h, x : x + w]
        glow_ratio = float(cv2.countNonZero(local_mask) / bbox_area)
        area_score = min(1.0, area / 4500.0)
        glow_score = min(1.0, glow_ratio / 0.42)
        shape_score = max(0.0, 1.0 - abs(np.log(max(0.05, aspect))) / 1.4)
        ring_score = min(1.0, circularity / 0.58) if circularity > 0 else 0.0
        score = 0.34 * area_score + 0.28 * glow_score + 0.22 * shape_score + 0.16 * ring_score
        candidates.append(
            PortalMainViewCandidate(
                score=float(score),
                area=area,
                glow_ratio=glow_ratio,
                circularity=circularity,
                aspect=aspect,
                bbox=(int(x), int(y), int(w), int(h)),
                center=(int(x + w / 2), int(y + h / 2)),
            )
        )
    candidates.sort(key=lambda item: item.score, reverse=True)
    return candidates, mask


def is_strict_portal_candidate(candidate: PortalMainViewCandidate, params: dict) -> bool:
    _x, _y, w, h = candidate.bbox
    aspect_skew = max(candidate.aspect, 1.0 / max(0.001, candidate.aspect))
    return (
        candidate.score >= float(params.get("threshold", 0.42))
        and w >= int(params.get("accept_min_width", 80))
        and h >= int(params.get("accept_min_height", 80))
        and candidate.area >= float(params.get("accept_min_area", 5000.0))
        and candidate.circularity >= float(params.get("accept_min_circularity", 0.45))
        and candidate.glow_ratio >= float(params.get("accept_min_glow", 0.30))
        and aspect_skew <= float(params.get("accept_max_aspect_skew", 1.65))
    )


def _load_params(path) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
