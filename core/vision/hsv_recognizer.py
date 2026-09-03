"""
HSV color recognizer facade.

The public `HSVRecognizer` class is the canonical recognizer entry point. Image
preprocessing, mask extraction, parameter application, and combined-mask
assembly live in sibling vision helper modules.
"""

import cv2
import numpy as np

from .hsv.combined import extract_combined_masks
from .hsv.masks import extract_fog_mask, extract_player_mask, extract_wall_mask, filter_small_components
from .hsv.params import apply_recognizer_params, recognizer_params
from .hsv.preprocessing import (
    compute_transparency_score,
    preprocess_for_fog,
    preprocess_for_wall,
    raw_gray_for_matching,
)


class HSVRecognizer:
    """HSV multi-layer recognizer facade."""

    def __init__(self):
        self.wall_hsv_min = np.array([118, 5, 54])
        self.wall_hsv_max = np.array([132, 90, 225])
        self.fog_hsv_min = np.array([91, 174, 188])
        self.fog_hsv_max = np.array([108, 243, 255])
        self.player_hsv_min = np.array([40, 100, 100])
        self.player_hsv_max = np.array([80, 255, 255])

        self.enable_wall = True
        self.enable_fog = True

        self.kernel_small = np.ones((3, 3), np.uint8)
        self.kernel_medium = np.ones((5, 5), np.uint8)

        self.edge_low = 50
        self.edge_high = 150
        self.wall_weight = 70
        self.edge_weight = 30

        self.clahe_enabled = True
        self.clahe_clip = 3.0
        self.clahe_grid = 4
        self._clahe = cv2.createCLAHE(
            clipLimit=self.clahe_clip,
            tileGridSize=(self.clahe_grid, self.clahe_grid),
        )

        self.deepen_enabled = True
        self.deepen_factor = 1.0
        self.blue_boost = 1.0

        self.gamma_enabled = True
        self.gamma_value = 2

        self.transparent_mode = True
        self.trans_wall_thresh = 50
        self.trans_sat_penalty = 1.5

        self.tophat_enabled = True
        self.tophat_kernel_size = 15
        self.tophat_strength = 4

        self.sat_filter_enabled = True
        self.sat_filter_thresh = 40
        self.player_clear_radius = 22
        self.sat_filter_radius = 0

    def get_params(self):
        return recognizer_params(self)

    def set_params(self, params):
        apply_recognizer_params(self, params)

    def _compute_transparency_score(self, img):
        return compute_transparency_score(self, img)

    def _preprocess_for_wall(self, img):
        return preprocess_for_wall(self, img)

    def _preprocess_for_fog(self, img):
        return preprocess_for_fog(self, img)

    def preprocess_image(self, img):
        return self._preprocess_for_wall(img)

    def get_raw_gray(self, img):
        return raw_gray_for_matching(self, img)

    def extract_walls(self, img, is_processed=False):
        return extract_wall_mask(self, img, is_processed=is_processed)

    def _filter_small_components(self, mask, min_area=20):
        return filter_small_components(mask, min_area=min_area)

    def extract_fog(self, img, is_processed=False):
        return extract_fog_mask(self, img, is_processed=is_processed)

    def extract_player(self, img, is_processed=False):
        return extract_player_mask(self, img, is_processed=is_processed)

    def extract_combined(self, img, player_pos=None):
        return extract_combined_masks(self, img, player_pos=player_pos)

    def get_preprocessed_image(self, img):
        return self.preprocess_image(img)
