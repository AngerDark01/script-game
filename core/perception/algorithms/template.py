from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import cv2
import numpy as np

from ..models import BoundingBox, CoordinateSpace, DetectionEvidence, FrameContext, TargetDetection


class TemplateDetector:
    """Multi-scale masked template detector for full-screen or local frames."""

    algorithm_id = "template"

    def __init__(
        self,
        target_type: str,
        template: np.ndarray | str | Path,
        parameters: Mapping[str, Any] | None = None,
    ) -> None:
        self.target_type = target_type
        self.parameters = dict(parameters or {})
        self.template, self.template_mask = self._load_template(template)

    def detect(self, frame: FrameContext) -> list[TargetDetection]:
        image = frame.image
        if image is None or not isinstance(image, np.ndarray) or image.size == 0:
            return []
        bgr = self._as_bgr(image)
        frame_gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        frame_edges = cv2.Canny(frame_gray, 50, 150)
        threshold = float(self.parameters.get("threshold", 0.75))
        top_k = max(1, int(self.parameters.get("top_k", 1)))
        edge_weight = min(1.0, max(0.0, float(self.parameters.get("edge_weight", 0.28))))
        scales = self._scales()
        hits: list[tuple[float, float, float, tuple[int, int], tuple[int, int]]] = []

        for scale in scales:
            template, mask = self._resize_template(scale)
            th, tw = template.shape[:2]
            if th <= 0 or tw <= 0 or th > bgr.shape[0] or tw > bgr.shape[1]:
                continue
            template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
            gray_response = _match_gray_response(frame_gray, template_gray)
            template_edges = cv2.Canny(template_gray, 50, 150)
            if int(np.count_nonzero(template_edges)) > 4:
                edge_response = _match_gray_response(frame_edges, template_edges)
                response = gray_response * (1.0 - edge_weight) + edge_response * edge_weight
            else:
                edge_response = np.zeros_like(gray_response)
                response = gray_response

            if mask is not None and int(np.count_nonzero(mask)) > 8:
                try:
                    masked = cv2.matchTemplate(bgr, template, cv2.TM_CCORR_NORMED, mask=mask)
                    masked = np.nan_to_num(masked, nan=-1.0, posinf=1.0, neginf=-1.0)
                    response = np.maximum(response, masked * 0.82 + gray_response * 0.18)
                except cv2.error:
                    pass

            suppress = max(4, min(tw, th) // 2)
            for score, top_left in _response_hits(response, top_k, threshold, suppress):
                x, y = top_left
                hits.append((score, float(gray_response[y, x]), float(edge_response[y, x]), (x, y), (tw, th)))

        detections: list[TargetDetection] = []
        for score, gray_score, edge_score, top_left, size in self._merge_hits(hits, top_k):
            x, y = top_left
            width, height = size
            bbox = BoundingBox(float(x), float(y), float(width), float(height))
            confidence = min(1.0, max(0.0, score))
            detections.append(
                TargetDetection(
                    target_type=self.target_type,
                    center=bbox.center,
                    coordinate_space=frame.coordinate_space or CoordinateSpace.FULL_SCREEN,
                    confidence=confidence,
                    bbox=bbox,
                    source=self.algorithm_id,
                    detected_at_ms=frame.captured_at_ms,
                    evidence=(
                        DetectionEvidence(
                            self.algorithm_id,
                            confidence,
                            {"gray_score": gray_score, "edge_score": edge_score, "scale": size[0] / self.template.shape[1]},
                        ),
                    ),
                )
            )
        return detections

    def _load_template(self, template: np.ndarray | str | Path) -> tuple[np.ndarray, np.ndarray | None]:
        if isinstance(template, (str, Path)):
            loaded = cv2.imread(str(template), cv2.IMREAD_UNCHANGED)
            if loaded is None:
                raise FileNotFoundError(f"template not readable: {template}")
        else:
            loaded = np.asarray(template)
        if loaded.size == 0:
            raise ValueError("template must not be empty")
        if loaded.ndim == 2:
            return cv2.cvtColor(loaded, cv2.COLOR_GRAY2BGR), None
        if loaded.ndim != 3 or loaded.shape[2] < 3:
            raise ValueError("template must be a grayscale, BGR, or BGRA image")
        mask = None
        if loaded.shape[2] >= 4:
            mask = np.where(loaded[:, :, 3] > 8, 255, 0).astype(np.uint8)
        return loaded[:, :, :3].copy(), mask

    @staticmethod
    def _as_bgr(image: np.ndarray) -> np.ndarray:
        if image.ndim == 2:
            return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        if image.ndim == 3 and image.shape[2] >= 3:
            return image[:, :, :3]
        raise ValueError("frame image must be grayscale, BGR, or BGRA")

    def _scales(self) -> list[float]:
        raw = self.parameters.get("scales", [1.0])
        if isinstance(raw, str):
            raw = [part.strip() for part in raw.split(",") if part.strip()]
        scales = [float(value) for value in raw]
        return [value for value in scales if value > 0] or [1.0]

    def _resize_template(self, scale: float) -> tuple[np.ndarray, np.ndarray | None]:
        height, width = self.template.shape[:2]
        size = (max(4, int(round(width * scale))), max(4, int(round(height * scale))))
        image = cv2.resize(self.template, size, interpolation=cv2.INTER_AREA)
        mask = None
        if self.template_mask is not None:
            mask = cv2.resize(self.template_mask, size, interpolation=cv2.INTER_NEAREST)
        return image, mask

    @staticmethod
    def _merge_hits(hits, top_k: int):
        selected = []
        for hit in sorted(hits, key=lambda item: item[0], reverse=True):
            _, _, _, center_top_left, size = hit
            cx = center_top_left[0] + size[0] / 2.0
            cy = center_top_left[1] + size[1] / 2.0
            duplicate = False
            for kept in selected:
                _, _, _, kept_top_left, kept_size = kept
                kx = kept_top_left[0] + kept_size[0] / 2.0
                ky = kept_top_left[1] + kept_size[1] / 2.0
                radius = max(12.0, min(size + kept_size) * 0.35)
                if float(np.hypot(cx - kx, cy - ky)) <= radius:
                    duplicate = True
                    break
            if not duplicate:
                selected.append(hit)
            if len(selected) >= top_k:
                break
        return selected


def _response_hits(response: np.ndarray, limit: int, threshold: float, suppress_radius: int):
    hits = []
    work = response.copy()
    for _ in range(limit):
        _, max_value, _, max_location = cv2.minMaxLoc(work)
        if max_value < threshold:
            break
        hits.append((float(max_value), max_location))
        x, y = max_location
        x1 = max(0, x - suppress_radius)
        y1 = max(0, y - suppress_radius)
        x2 = min(work.shape[1], x + suppress_radius + 1)
        y2 = min(work.shape[0], y + suppress_radius + 1)
        work[y1:y2, x1:x2] = -1.0
    return hits


def _match_gray_response(frame: np.ndarray, template: np.ndarray) -> np.ndarray:
    """Use squared difference for low-texture templates to avoid correlation degeneracy."""
    if float(np.std(template)) < 1.0:
        response = cv2.matchTemplate(frame, template, cv2.TM_SQDIFF_NORMED)
        response = 1.0 - response
    else:
        response = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)
    return np.nan_to_num(response, nan=-1.0, posinf=1.0, neginf=-1.0)
