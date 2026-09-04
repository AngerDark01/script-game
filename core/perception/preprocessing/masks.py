"""Pure binary-mask, morphology, and mask-composition operations."""

from __future__ import annotations

import math

import cv2
import numpy as np

from .image_ops import to_hsv


def hsv_range_mask(
    hsv_image: np.ndarray,
    *,
    lower: tuple[int, int, int],
    upper: tuple[int, int, int],
) -> np.ndarray:
    """Build a binary mask from an already-HSV three-channel image."""
    source = _hsv_uint8(hsv_image)
    lower_bound = _hsv_bound("lower", lower)
    upper_bound = _hsv_bound("upper", upper)
    if any(lower_bound[index] > upper_bound[index] for index in range(3)):
        raise ValueError("lower HSV bound must not exceed upper bound")
    return cv2.inRange(source, lower_bound, upper_bound)


def binary_threshold(image: np.ndarray, *, threshold: int) -> np.ndarray:
    """Convert a single-channel image into a binary mask."""
    source = _mask_uint8(image)
    if not isinstance(threshold, int) or isinstance(threshold, bool) or not 0 <= threshold <= 255:
        raise ValueError("threshold must be an integer from 0 to 255")
    _, result = cv2.threshold(source, threshold, 255, cv2.THRESH_BINARY)
    return result


def morphology(
    mask: np.ndarray,
    *,
    operation: str,
    kernel_shape: str,
    kernel_size: int,
    iterations: int = 1,
) -> np.ndarray:
    """Apply binary morphology with an explicit operation and kernel shape."""
    source = _mask_uint8(mask)
    if not isinstance(kernel_size, int) or isinstance(kernel_size, bool) or kernel_size <= 0:
        raise ValueError("kernel_size must be a positive integer")
    if not isinstance(iterations, int) or isinstance(iterations, bool) or iterations < 0:
        raise ValueError("iterations must be a non-negative integer")
    shapes = {
        "rect": cv2.MORPH_RECT,
        "cross": cv2.MORPH_CROSS,
        "ellipse": cv2.MORPH_ELLIPSE,
    }
    operations = {
        "open": cv2.MORPH_OPEN,
        "close": cv2.MORPH_CLOSE,
    }
    if kernel_shape not in shapes:
        raise ValueError(f"unsupported kernel_shape: {kernel_shape}")
    kernel = cv2.getStructuringElement(shapes[kernel_shape], (kernel_size, kernel_size))
    if operation in operations:
        return cv2.morphologyEx(source, operations[operation], kernel, iterations=iterations)
    if operation == "dilate":
        return cv2.dilate(source, kernel, iterations=iterations)
    if operation == "erode":
        return cv2.erode(source, kernel, iterations=iterations)
    raise ValueError(f"unsupported morphology operation: {operation}")


def filter_small_components(mask: np.ndarray, *, min_area: int) -> np.ndarray:
    """Remove 8-connected components whose pixel area is smaller than min_area."""
    source = _mask_uint8(mask)
    if not isinstance(min_area, int) or isinstance(min_area, bool) or min_area < 0:
        raise ValueError("min_area must be a non-negative integer")
    labels_count, labels, statistics, _ = cv2.connectedComponentsWithStats(source, connectivity=8)
    result = np.zeros_like(source)
    for index in range(1, labels_count):
        if int(statistics[index, cv2.CC_STAT_AREA]) >= min_area:
            result[labels == index] = 255
    return result


def saturation_mask(image: np.ndarray, *, threshold: int) -> np.ndarray:
    """Return a binary mask where HSV saturation is above a configurable threshold."""
    if not isinstance(threshold, int) or isinstance(threshold, bool) or not 0 <= threshold <= 255:
        raise ValueError("threshold must be an integer from 0 to 255")
    saturation = to_hsv(image)[..., 1]
    return np.where(saturation > threshold, 255, 0).astype(np.uint8)


def circle_mask(
    shape: tuple[int, int],
    *,
    center: tuple[int, int],
    radius: int,
    inside: int = 255,
    outside: int = 0,
) -> np.ndarray:
    """Create a single-channel circle mask without attaching it to a game target."""
    if len(shape) != 2 or any(not isinstance(value, int) or value <= 0 for value in shape):
        raise ValueError("shape must contain positive (height, width)")
    if len(center) != 2 or any(not isinstance(value, int) for value in center):
        raise ValueError("center must contain integer coordinates")
    if not isinstance(radius, int) or isinstance(radius, bool) or radius < 0:
        raise ValueError("radius must be a non-negative integer")
    if any(not isinstance(value, int) or not 0 <= value <= 255 for value in (inside, outside)):
        raise ValueError("inside and outside must be uint8 values")
    result = np.full(shape, outside, dtype=np.uint8)
    cv2.circle(result, center, radius, inside, -1)
    return result


def subtract_mask(mask: np.ndarray, exclusion_mask: np.ndarray) -> np.ndarray:
    """Clear all pixels selected by an equally-sized exclusion mask."""
    source = _mask_uint8(mask)
    exclusion = _mask_uint8(exclusion_mask)
    if source.shape != exclusion.shape:
        raise ValueError("mask and exclusion_mask must have the same shape")
    return cv2.bitwise_and(source, cv2.bitwise_not(exclusion))


def intersect_masks(first: np.ndarray, second: np.ndarray) -> np.ndarray:
    """Keep only pixels selected by both equally-sized masks."""
    first_mask = _mask_uint8(first)
    second_mask = _mask_uint8(second)
    if first_mask.shape != second_mask.shape:
        raise ValueError("masks must have the same shape")
    return cv2.bitwise_and(first_mask, second_mask)


def weighted_mask_fusion(
    *,
    first: np.ndarray,
    first_weight: float,
    second: np.ndarray,
    second_weight: float,
) -> np.ndarray:
    """Blend same-sized masks by their non-negative normalized weights."""
    first_mask = _mask_uint8(first)
    second_mask = _mask_uint8(second)
    if first_mask.shape != second_mask.shape:
        raise ValueError("masks must have the same shape")
    weights = (float(first_weight), float(second_weight))
    if any(not math.isfinite(value) or value < 0 for value in weights):
        raise ValueError("mask weights must be finite non-negative numbers")
    total = max(1.0, sum(weights))
    return cv2.addWeighted(
        first_mask,
        weights[0] / total,
        second_mask,
        weights[1] / total,
        0,
    )


def _mask_uint8(mask: np.ndarray) -> np.ndarray:
    if not isinstance(mask, np.ndarray) or mask.ndim != 2 or mask.size == 0:
        raise ValueError("mask must be a non-empty two-dimensional numpy array")
    if mask.dtype == np.uint8:
        return mask
    return np.clip(mask, 0, 255).astype(np.uint8)


def _hsv_uint8(image: np.ndarray) -> np.ndarray:
    if not isinstance(image, np.ndarray) or image.ndim != 3 or image.shape[2] != 3 or image.size == 0:
        raise ValueError("hsv_image must be a non-empty three-channel numpy array")
    if image.dtype == np.uint8:
        return image
    return np.clip(image, 0, 255).astype(np.uint8)


def _hsv_bound(name: str, bound: tuple[int, int, int]) -> np.ndarray:
    if len(bound) != 3 or any(not isinstance(value, int) or not 0 <= value <= 255 for value in bound):
        raise ValueError(f"{name} must contain three uint8 values")
    return np.array(bound, dtype=np.uint8)
