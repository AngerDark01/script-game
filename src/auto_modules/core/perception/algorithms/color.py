from __future__ import annotations

from typing import Any, Mapping

import cv2
import numpy as np

from ..models import BoundingBox, DetectionEvidence, FrameContext, TargetDetection


class ColorRegionDetector:
    """Find connected regions selected by configurable HSV bounds."""

    algorithm_id = "color"

    def __init__(self, target_type: str, parameters: Mapping[str, Any] | None = None) -> None:
        self.target_type = target_type
        self.parameters = dict(parameters or {})

    def detect(self, frame: FrameContext) -> list[TargetDetection]:
        image = frame.image
        if image is None or not isinstance(image, np.ndarray) or image.size == 0:
            return []
        if image.ndim == 2:
            bgr = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        elif image.ndim == 3 and image.shape[2] >= 3:
            bgr = image[:, :, :3]
        else:
            return []

        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        mask = self._build_mask(hsv)
        kernel_size = max(0, int(self.parameters.get("morphology_kernel", 0)))
        if kernel_size > 1:
            kernel_size = kernel_size if kernel_size % 2 else kernel_size + 1
            kernel = np.ones((kernel_size, kernel_size), dtype=np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        min_area = max(0, float(self.parameters.get("min_area", 1)))
        max_area = max(0, float(self.parameters.get("max_area", 0)))
        confidence_floor = min(1.0, max(0.0, float(self.parameters.get("confidence_floor", 0.5))))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        detections: list[TargetDetection] = []
        for contour in contours:
            area = float(cv2.contourArea(contour))
            if area < min_area or (max_area > 0 and area > max_area):
                continue
            x, y, width, height = cv2.boundingRect(contour)
            if width <= 0 or height <= 0:
                continue
            fill_ratio = min(1.0, area / float(width * height))
            confidence = confidence_floor + (1.0 - confidence_floor) * fill_ratio
            bbox = BoundingBox(float(x), float(y), float(width), float(height))
            detections.append(
                TargetDetection(
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
                            {"area": area, "fill_ratio": fill_ratio},
                        ),
                    ),
                )
            )
        return sorted(detections, key=lambda item: item.confidence, reverse=True)

    def _build_mask(self, hsv: np.ndarray) -> np.ndarray:
        hue_min = int(self.parameters.get("hue_min", 0))
        hue_max = int(self.parameters.get("hue_max", 179))
        sat_min = int(self.parameters.get("saturation_min", 0))
        sat_max = int(self.parameters.get("saturation_max", 255))
        value_min = int(self.parameters.get("value_min", 0))
        value_max = int(self.parameters.get("value_max", 255))
        lower = np.array([max(0, hue_min), max(0, sat_min), max(0, value_min)], dtype=np.uint8)
        upper = np.array([min(179, hue_max), min(255, sat_max), min(255, value_max)], dtype=np.uint8)
        if hue_min <= hue_max:
            return cv2.inRange(hsv, lower, upper)
        # Hue wraps at 180 in OpenCV's HSV representation.
        first = cv2.inRange(hsv, lower, np.array([179, upper[1], upper[2]], dtype=np.uint8))
        second = cv2.inRange(hsv, np.array([0, lower[1], lower[2]], dtype=np.uint8), upper)
        return cv2.bitwise_or(first, second)
