from __future__ import annotations

from math import isfinite, pi
from typing import Any, Mapping

import cv2
import numpy as np

from ..models import BoundingBox, DetectionEvidence, FrameContext, TargetDetection


class ShapeDetector:
    """Detect thresholded contours that satisfy reusable geometric filters."""

    algorithm_id = "shape"

    def __init__(self, target_type: str, parameters: Mapping[str, Any] | None = None) -> None:
        self.target_type = str(target_type)
        self.parameters = dict(parameters or {})
        self.threshold = self._integer("threshold", 128, minimum=0, maximum=255)
        self.threshold_mode = str(self.parameters.get("threshold_mode", "binary")).strip().lower()
        if self.threshold_mode not in {"binary", "binary_inverse"}:
            raise ValueError("threshold_mode must be binary or binary_inverse")
        self.morphology_kernel = self._integer("morphology_kernel", 0, minimum=0)
        self.min_area = self._number("min_area", 1.0, minimum=0.0)
        self.max_area = self._number("max_area", 0.0, minimum=0.0)
        if self.max_area and self.max_area < self.min_area:
            raise ValueError("max_area must be zero or at least min_area")
        self.min_vertices = self._integer("min_vertices", 0, minimum=0)
        self.max_vertices = self._integer("max_vertices", 0, minimum=0)
        if self.max_vertices and self.max_vertices < self.min_vertices:
            raise ValueError("max_vertices must be zero or at least min_vertices")
        self.approximation_ratio = self._number("approximation_ratio", 0.02, minimum=0.0)
        if self.approximation_ratio <= 0.0:
            raise ValueError("approximation_ratio must be positive")
        self.min_circularity = self._number("min_circularity", 0.0, minimum=0.0, maximum=1.0)
        self.min_solidity = self._number("min_solidity", 0.0, minimum=0.0, maximum=1.0)
        raw_max_results = self._integer("max_results", 0, minimum=0)
        self.max_results = raw_max_results or None

    def detect(self, frame: FrameContext) -> list[TargetDetection]:
        """Extract accepted external contours from a normalized frame."""
        gray = self._as_gray(frame.image)
        if gray is None:
            return []
        threshold_type = cv2.THRESH_BINARY if self.threshold_mode == "binary" else cv2.THRESH_BINARY_INV
        _, mask = cv2.threshold(gray, self.threshold, 255, threshold_type)
        mask = self._morphology(mask)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        detections: list[TargetDetection] = []
        for contour in contours:
            detection = self._to_detection(contour, frame)
            if detection is not None:
                detections.append(detection)
        detections.sort(key=lambda item: item.confidence, reverse=True)
        return detections if self.max_results is None else detections[: self.max_results]

    def _to_detection(self, contour: np.ndarray, frame: FrameContext) -> TargetDetection | None:
        area = float(cv2.contourArea(contour))
        if area < self.min_area or (self.max_area > 0.0 and area > self.max_area):
            return None
        perimeter = float(cv2.arcLength(contour, True))
        if perimeter <= 0.0:
            return None
        vertices = int(len(cv2.approxPolyDP(contour, self.approximation_ratio * perimeter, True)))
        if vertices < self.min_vertices or (self.max_vertices > 0 and vertices > self.max_vertices):
            return None
        x, y, width, height = cv2.boundingRect(contour)
        if width <= 0 or height <= 0:
            return None
        hull_area = float(cv2.contourArea(cv2.convexHull(contour)))
        solidity = min(1.0, area / hull_area) if hull_area > 0.0 else 0.0
        circularity = min(1.0, 4.0 * pi * area / (perimeter * perimeter))
        if circularity < self.min_circularity or solidity < self.min_solidity:
            return None
        fill_ratio = min(1.0, area / float(width * height))
        confidence = (fill_ratio + solidity) / 2.0
        bbox = BoundingBox(float(x), float(y), float(width), float(height))
        return TargetDetection(
            target_type=self.target_type,
            center=bbox.center,
            coordinate_space=frame.coordinate_space,
            confidence=confidence,
            bbox=bbox,
            source=self.algorithm_id,
            detected_at_ms=frame.captured_at_ms,
            evidence=(
                DetectionEvidence(
                    self.algorithm_id,
                    confidence,
                    {
                        "area": area,
                        "perimeter": perimeter,
                        "vertices": vertices,
                        "circularity": circularity,
                        "solidity": solidity,
                        "fill_ratio": fill_ratio,
                        "threshold_mode": self.threshold_mode,
                    },
                ),
            ),
        )

    def _morphology(self, mask: np.ndarray) -> np.ndarray:
        if self.morphology_kernel <= 1:
            return mask
        size = self.morphology_kernel if self.morphology_kernel % 2 else self.morphology_kernel + 1
        kernel = np.ones((size, size), dtype=np.uint8)
        opened = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        return cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel)

    @staticmethod
    def _as_gray(image: Any) -> np.ndarray | None:
        if image is None or not isinstance(image, np.ndarray) or image.size == 0:
            return None
        if image.ndim == 2:
            return image
        if image.ndim == 3 and image.shape[2] >= 3:
            return cv2.cvtColor(image[:, :, :3], cv2.COLOR_BGR2GRAY)
        return None

    def _integer(self, name: str, default: int, *, minimum: int = 0, maximum: int | None = None) -> int:
        value = int(self.parameters.get(name, default))
        if value < minimum or (maximum is not None and value > maximum):
            suffix = f" and at most {maximum}" if maximum is not None else ""
            raise ValueError(f"{name} must be at least {minimum}{suffix}")
        return value

    def _number(self, name: str, default: float, *, minimum: float, maximum: float | None = None) -> float:
        value = float(self.parameters.get(name, default))
        if not isfinite(value) or value < minimum or (maximum is not None and value > maximum):
            suffix = f" and at most {maximum}" if maximum is not None else ""
            raise ValueError(f"{name} must be at least {minimum}{suffix}")
        return value
