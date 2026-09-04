"""Pure, game-agnostic pixel enhancement and colour-space operations."""

from __future__ import annotations

import math

import cv2
import numpy as np


def gamma_correct(image: np.ndarray, *, gamma: float) -> np.ndarray:
    """Apply the historical 8-bit gamma lookup-table transform."""
    source = _image_uint8(image)
    if not math.isfinite(float(gamma)) or float(gamma) <= 0:
        raise ValueError("gamma must be a finite positive number")
    table = np.array(
        [((index / 255.0) ** float(gamma)) * 255 for index in range(256)],
        dtype=np.uint8,
    )
    return cv2.LUT(source, table)


def gaussian_blur(image: np.ndarray, *, kernel_size: int = 3) -> np.ndarray:
    """Blur an image with an odd square Gaussian kernel."""
    source = _image_uint8(image)
    _odd_kernel_size(kernel_size)
    return cv2.GaussianBlur(source, (kernel_size, kernel_size), 0)


def median_blur(image: np.ndarray, *, kernel_size: int = 3) -> np.ndarray:
    """Denoise an image with an odd square median kernel."""
    source = _image_uint8(image)
    _odd_kernel_size(kernel_size)
    return cv2.medianBlur(source, kernel_size)


def lab_clahe(
    image: np.ndarray,
    *,
    clip_limit: float = 2.0,
    tile_grid_size: tuple[int, int] = (8, 8),
) -> np.ndarray:
    """Apply CLAHE to L only while retaining BGR chroma."""
    source = _bgr_uint8(image)
    if not math.isfinite(float(clip_limit)) or float(clip_limit) <= 0:
        raise ValueError("clip_limit must be a finite positive number")
    if len(tile_grid_size) != 2 or any(not isinstance(value, int) or value <= 0 for value in tile_grid_size):
        raise ValueError("tile_grid_size must contain two positive integers")
    lab = cv2.cvtColor(source, cv2.COLOR_BGR2LAB)
    lightness, channel_a, channel_b = cv2.split(lab)
    enhanced = cv2.createCLAHE(
        clipLimit=float(clip_limit),
        tileGridSize=(int(tile_grid_size[0]), int(tile_grid_size[1])),
    ).apply(lightness)
    return cv2.cvtColor(cv2.merge((enhanced, channel_a, channel_b)), cv2.COLOR_LAB2BGR)


def top_hat(image: np.ndarray, *, kernel_size: int, strength: float = 1.0) -> np.ndarray:
    """Return a scaled top-hat response for grayscale or BGR images."""
    source = _image_uint8(image)
    _odd_kernel_size(kernel_size)
    if not math.isfinite(float(strength)) or float(strength) < 0:
        raise ValueError("strength must be a finite non-negative number")
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
    response = cv2.morphologyEx(source, cv2.MORPH_TOPHAT, kernel)
    return cv2.convertScaleAbs(response, alpha=float(strength), beta=0)


def add_top_hat(image: np.ndarray, *, kernel_size: int, strength: float = 1.0) -> np.ndarray:
    """Add a top-hat response back into an image using saturating 8-bit arithmetic."""
    source = _image_uint8(image)
    return cv2.add(source, top_hat(source, kernel_size=kernel_size, strength=strength))


def percentile_normalize(image: np.ndarray, *, low: float, high: float) -> np.ndarray:
    """Stretch an image between two percentiles, retaining flat inputs unchanged."""
    source = _image_uint8(image)
    if not 0 <= float(low) <= 100 or not 0 <= float(high) <= 100 or float(high) < float(low):
        raise ValueError("low and high must be ordered percentiles between 0 and 100")
    min_value = np.percentile(source, float(low))
    max_value = np.percentile(source, float(high))
    if max_value <= min_value:
        return source.copy()
    normalized = (source.astype(np.float32) - min_value) * 255.0 / (max_value - min_value)
    return np.clip(normalized, 0, 255).astype(np.uint8)


def scale_intensity(image: np.ndarray, *, alpha: float = 1.0, beta: float = 0.0) -> np.ndarray:
    """Apply OpenCV-compatible absolute linear intensity scaling."""
    source = _image_uint8(image)
    if not math.isfinite(float(alpha)) or not math.isfinite(float(beta)):
        raise ValueError("alpha and beta must be finite")
    return cv2.convertScaleAbs(source, alpha=float(alpha), beta=float(beta))


def scale_bgr_channels(
    image: np.ndarray,
    *,
    blue: float = 1.0,
    green: float = 1.0,
    red: float = 1.0,
) -> np.ndarray:
    """Scale BGR channels independently with clipping."""
    source = _bgr_uint8(image)
    scales = (blue, green, red)
    if any(not math.isfinite(float(value)) or float(value) < 0 for value in scales):
        raise ValueError("channel scales must be finite non-negative numbers")
    channels = cv2.split(source)
    return cv2.merge(
        tuple(
            np.clip(cv2.multiply(channel, float(scale)), 0, 255).astype(np.uint8)
            for channel, scale in zip(channels, scales)
        )
    )


def to_gray(image: np.ndarray) -> np.ndarray:
    """Convert gray, BGR, or BGRA input to a single gray channel."""
    source = _image_uint8(image)
    if source.ndim == 2:
        return source.copy()
    if source.shape[2] == 3:
        return cv2.cvtColor(source, cv2.COLOR_BGR2GRAY)
    if source.shape[2] == 4:
        return cv2.cvtColor(source, cv2.COLOR_BGRA2GRAY)
    raise ValueError("image must have one, three, or four channels")


def to_hsv(image: np.ndarray) -> np.ndarray:
    """Convert gray, BGR, or BGRA input to three-channel HSV."""
    source = _image_uint8(image)
    if source.ndim == 2:
        return cv2.cvtColor(
            cv2.cvtColor(source, cv2.COLOR_GRAY2BGR),
            cv2.COLOR_BGR2HSV,
        )
    if source.shape[2] == 3:
        return cv2.cvtColor(source, cv2.COLOR_BGR2HSV)
    if source.shape[2] == 4:
        return cv2.cvtColor(
            cv2.cvtColor(source, cv2.COLOR_BGRA2BGR),
            cv2.COLOR_BGR2HSV,
        )
    raise ValueError("image must have one, three, or four channels")


def canny_edges(image: np.ndarray, *, low: int, high: int) -> np.ndarray:
    """Produce a single-channel Canny edge mask from any supported image input."""
    if not isinstance(low, int) or not isinstance(high, int) or low < 0 or high < 0 or high < low:
        raise ValueError("low and high must be ordered non-negative integers")
    return cv2.Canny(to_gray(image), low, high)


def _image_uint8(image: np.ndarray) -> np.ndarray:
    if not isinstance(image, np.ndarray) or image.ndim not in (2, 3) or image.size == 0:
        raise ValueError("image must be a non-empty 2D or 3D numpy array")
    if image.dtype == np.uint8:
        return image
    return np.clip(image, 0, 255).astype(np.uint8)


def _bgr_uint8(image: np.ndarray) -> np.ndarray:
    source = _image_uint8(image)
    if source.ndim != 3 or source.shape[2] != 3:
        raise ValueError("image must be a three-channel BGR array")
    return source


def _odd_kernel_size(kernel_size: int) -> None:
    if not isinstance(kernel_size, int) or isinstance(kernel_size, bool) or kernel_size <= 0 or kernel_size % 2 == 0:
        raise ValueError("kernel_size must be a positive odd integer")
