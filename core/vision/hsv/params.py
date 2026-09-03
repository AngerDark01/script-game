from __future__ import annotations

import cv2
import numpy as np


def recognizer_params(recognizer) -> dict:
    return {
        "wall_hsv_min": recognizer.wall_hsv_min.tolist(),
        "wall_hsv_max": recognizer.wall_hsv_max.tolist(),
        "fog_hsv_min": recognizer.fog_hsv_min.tolist(),
        "fog_hsv_max": recognizer.fog_hsv_max.tolist(),
        "player_hsv_min": recognizer.player_hsv_min.tolist(),
        "player_hsv_max": recognizer.player_hsv_max.tolist(),
        "enable_wall": recognizer.enable_wall,
        "enable_fog": recognizer.enable_fog,
        "clahe_enabled": recognizer.clahe_enabled,
        "deepen_enabled": recognizer.deepen_enabled,
        "gamma_enabled": recognizer.gamma_enabled,
        "tophat_enabled": recognizer.tophat_enabled,
        "sat_filter_enabled": recognizer.sat_filter_enabled,
        "clahe_clip": recognizer.clahe_clip,
        "clahe_grid": recognizer.clahe_grid,
        "deepen_factor": recognizer.deepen_factor,
        "blue_boost": recognizer.blue_boost,
        "gamma_value": recognizer.gamma_value,
        "tophat_strength": recognizer.tophat_strength,
        "tophat_kernel_size": recognizer.tophat_kernel_size,
        "trans_sat_penalty": recognizer.trans_sat_penalty,
        "trans_wall_thresh": recognizer.trans_wall_thresh,
        "transparent_mode": recognizer.transparent_mode,
        "sat_filter_thresh": recognizer.sat_filter_thresh,
        "sat_filter_radius": recognizer.sat_filter_radius,
        "player_clear_radius": recognizer.player_clear_radius,
        "wall_weight": recognizer.wall_weight,
        "edge_weight": recognizer.edge_weight,
        "edge_low": recognizer.edge_low,
        "edge_high": recognizer.edge_high,
        "kernel_small_size": recognizer.kernel_small.shape[0],
        "kernel_medium_size": recognizer.kernel_medium.shape[0],
    }


def apply_recognizer_params(recognizer, params) -> None:
    if "wall_hsv_min" in params:
        recognizer.wall_hsv_min = np.array(params["wall_hsv_min"])
    if "wall_hsv_max" in params:
        recognizer.wall_hsv_max = np.array(params["wall_hsv_max"])
    if "fog_hsv_min" in params:
        recognizer.fog_hsv_min = np.array(params["fog_hsv_min"])
    if "fog_hsv_max" in params:
        recognizer.fog_hsv_max = np.array(params["fog_hsv_max"])
    if "player_hsv_min" in params:
        recognizer.player_hsv_min = np.array(params["player_hsv_min"])
    if "player_hsv_max" in params:
        recognizer.player_hsv_max = np.array(params["player_hsv_max"])

    if "enable_wall" in params:
        recognizer.enable_wall = params["enable_wall"]
    if "enable_fog" in params:
        recognizer.enable_fog = params["enable_fog"]
    if "clahe_enabled" in params:
        recognizer.clahe_enabled = params["clahe_enabled"]
    if "deepen_enabled" in params:
        recognizer.deepen_enabled = params["deepen_enabled"]
    if "gamma_enabled" in params:
        recognizer.gamma_enabled = params["gamma_enabled"]
    if "tophat_enabled" in params:
        recognizer.tophat_enabled = params["tophat_enabled"]
    if "sat_filter_enabled" in params:
        recognizer.sat_filter_enabled = params["sat_filter_enabled"]

    if "clahe_clip" in params:
        recognizer.clahe_clip = params["clahe_clip"]
        recognizer._clahe.setClipLimit(recognizer.clahe_clip)
    if "clahe_grid" in params:
        recognizer.clahe_grid = params["clahe_grid"]
        recognizer._clahe = cv2.createCLAHE(
            clipLimit=recognizer.clahe_clip,
            tileGridSize=(recognizer.clahe_grid, recognizer.clahe_grid),
        )

    if "deepen_factor" in params:
        recognizer.deepen_factor = params["deepen_factor"]
    if "blue_boost" in params:
        recognizer.blue_boost = params["blue_boost"]
    if "gamma_value" in params:
        recognizer.gamma_value = params["gamma_value"]
    if "tophat_strength" in params:
        recognizer.tophat_strength = params["tophat_strength"]
    if "tophat_kernel_size" in params:
        recognizer.tophat_kernel_size = params["tophat_kernel_size"]
    if "trans_sat_penalty" in params:
        recognizer.trans_sat_penalty = params["trans_sat_penalty"]
    if "trans_wall_thresh" in params:
        recognizer.trans_wall_thresh = params["trans_wall_thresh"]
    if "transparent_mode" in params:
        recognizer.transparent_mode = params["transparent_mode"]
    if "sat_filter_thresh" in params:
        recognizer.sat_filter_thresh = params["sat_filter_thresh"]
    if "sat_filter_radius" in params:
        recognizer.sat_filter_radius = params["sat_filter_radius"]
    if "player_clear_radius" in params:
        recognizer.player_clear_radius = max(0, int(params["player_clear_radius"]))

    if "wall_weight" in params:
        recognizer.wall_weight = params["wall_weight"]
    if "edge_weight" in params:
        recognizer.edge_weight = params["edge_weight"]
    if "edge_low" in params:
        recognizer.edge_low = params["edge_low"]
    if "edge_high" in params:
        recognizer.edge_high = params["edge_high"]

    if "kernel_small_size" in params:
        size = int(params["kernel_small_size"])
        recognizer.kernel_small = np.ones((size, size), np.uint8)
    if "kernel_medium_size" in params:
        size = int(params["kernel_medium_size"])
        recognizer.kernel_medium = np.ones((size, size), np.uint8)
