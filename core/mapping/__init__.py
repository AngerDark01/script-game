"""Mapping and map package helper modules."""

from .frame_preparation import (
    bounds_in_canvas,
    is_too_similar,
    prepare_scaled_frame_masks,
    scaled_player_pos,
    standardize_wall_thickness,
)
from .frame_pipeline import add_frame_to_stitcher
from .package_io import load_stitcher_map_package, save_stitcher_map_package
from .performance import PerformanceMonitor, Timer
from .rendering import get_cropped_map, get_enhanced_map
from .stitcher import MapStitcher
from .weighted_merge import merge_frame_weighted

__all__ = [
    "MapStitcher",
    "PerformanceMonitor",
    "Timer",
    "add_frame_to_stitcher",
    "bounds_in_canvas",
    "get_cropped_map",
    "get_enhanced_map",
    "is_too_similar",
    "load_stitcher_map_package",
    "merge_frame_weighted",
    "prepare_scaled_frame_masks",
    "save_stitcher_map_package",
    "scaled_player_pos",
    "standardize_wall_thickness",
]
