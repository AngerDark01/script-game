from __future__ import annotations

import cv2
import numpy as np


def bgr_to_hsv(image):
    return cv2.cvtColor(image, cv2.COLOR_BGR2HSV)


def hsv_values_at_points(hsv_image, points):
    return [hsv_image[y, x] for x, y in points]


def calculate_hsv_range(hsv_values) -> tuple:
    hsv_array = np.array(hsv_values)
    mean_hsv = np.mean(hsv_array, axis=0)
    std_hsv = np.std(hsv_array, axis=0)
    tolerance = np.maximum(std_hsv * 2, [5, 20, 20])
    min_hsv = np.maximum(mean_hsv - tolerance, [0, 0, 0])
    max_hsv = np.minimum(mean_hsv + tolerance, [179, 255, 255])
    return mean_hsv, min_hsv.astype(int), max_hsv.astype(int)


def mean_saturation(hsv_values) -> float:
    return float(np.mean([value[1] for value in hsv_values]))

