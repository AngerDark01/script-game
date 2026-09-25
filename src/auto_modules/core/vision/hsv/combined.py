from __future__ import annotations

import numpy as np

from auto_modules.core.perception.preprocessing.image_ops import canny_edges, to_gray
from auto_modules.core.perception.preprocessing.masks import (
    circle_mask,
    intersect_masks,
    morphology,
    saturation_mask,
    subtract_mask,
    weighted_mask_fusion,
)


def extract_combined_masks(recognizer, img, player_pos=None, *, processed_for_wall=None):
    img_wall_processed = (
        processed_for_wall
        if processed_for_wall is not None
        else recognizer._preprocess_for_wall(img)
    )
    wall_mask = recognizer.extract_walls(img_wall_processed, is_processed=True)
    fog_mask = recognizer.extract_fog(img, is_processed=False)

    gray = to_gray(img_wall_processed)
    edges = canny_edges(gray, low=recognizer.edge_low, high=recognizer.edge_high)

    if recognizer.sat_filter_enabled:
        dynamic_mask = dynamic_color_mask(recognizer, img, player_pos=player_pos)
        wall_mask[dynamic_mask] = 0
        fog_mask[dynamic_mask] = 0
        edges[dynamic_mask] = 0

    h, w = wall_mask.shape
    if player_pos:
        cx, cy = player_pos
    else:
        cx, cy = w // 2, h // 2

    radius = int(recognizer.player_clear_radius)
    if radius > 0:
        player_exclusion = circle_mask(
            wall_mask.shape,
            center=(cx, cy),
            radius=radius,
        )
        wall_mask = subtract_mask(wall_mask, player_exclusion)
        fog_mask = subtract_mask(fog_mask, player_exclusion)
        edges = subtract_mask(edges, player_exclusion)

    match_mask = weighted_match_mask(recognizer, wall_mask, edges)
    if radius > 0:
        match_mask = subtract_mask(match_mask, player_exclusion)

    return match_mask.astype(np.uint8), wall_mask, fog_mask


def dynamic_color_mask(recognizer, img, player_pos=None):
    dynamic_mask = saturation_mask(img, threshold=recognizer.sat_filter_thresh)

    if recognizer.sat_filter_radius > 0:
        h_img, w_img = img.shape[:2]
        if player_pos:
            cx_p, cy_p = player_pos
        else:
            cx_p, cy_p = w_img // 2, h_img // 2
        dynamic_mask = intersect_masks(
            dynamic_mask,
            circle_mask(
                (h_img, w_img),
                center=(cx_p, cy_p),
                radius=recognizer.sat_filter_radius,
            ),
        )

    return morphology(
        dynamic_mask,
        operation="dilate",
        kernel_shape="rect",
        kernel_size=recognizer.kernel_small.shape[0],
    ) > 0


def weighted_match_mask(recognizer, wall_mask, edges):
    wall_weight = max(0, recognizer.wall_weight)
    edge_weight = max(0, recognizer.edge_weight)
    return weighted_mask_fusion(
        first=wall_mask,
        first_weight=wall_weight,
        second=edges,
        second_weight=edge_weight,
    )
