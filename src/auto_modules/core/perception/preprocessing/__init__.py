"""Game-agnostic image preprocessing contracts and operations."""

from .models import ImageArtifact, ImageGeometry, Matrix3x3
from .geometry import crop, pad, resize
from .image_ops import (
    add_top_hat,
    canny_edges,
    gamma_correct,
    gaussian_blur,
    lab_clahe,
    median_blur,
    percentile_normalize,
    scale_bgr_channels,
    scale_intensity,
    to_gray,
    to_hsv,
    top_hat,
)
from .masks import (
    binary_threshold,
    circle_mask,
    filter_small_components,
    hsv_range_mask,
    intersect_masks,
    morphology,
    saturation_mask,
    subtract_mask,
    weighted_mask_fusion,
)

__all__ = [
    "ImageArtifact",
    "ImageGeometry",
    "Matrix3x3",
    "add_top_hat",
    "binary_threshold",
    "canny_edges",
    "circle_mask",
    "crop",
    "filter_small_components",
    "gamma_correct",
    "gaussian_blur",
    "lab_clahe",
    "median_blur",
    "morphology",
    "pad",
    "percentile_normalize",
    "resize",
    "scale_bgr_channels",
    "scale_intensity",
    "saturation_mask",
    "subtract_mask",
    "to_gray",
    "to_hsv",
    "top_hat",
    "hsv_range_mask",
    "intersect_masks",
    "weighted_mask_fusion",
]
