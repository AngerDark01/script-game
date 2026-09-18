from __future__ import annotations

import cv2
import numpy as np


def minimap_environment_signature(frame, player_pos) -> np.ndarray | None:
    """Build a compact grayscale signature around the minimap player position."""
    if frame is None:
        return None
    if player_pos is None:
        center_x = frame.shape[1] // 2
        center_y = frame.shape[0] // 2
    else:
        center_x = int(player_pos[0])
        center_y = int(player_pos[1])
    half = 46
    left = max(0, center_x - half)
    right = min(frame.shape[1], center_x + half)
    top = max(0, center_y - half)
    bottom = min(frame.shape[0], center_y + half)
    patch = frame[top:bottom, left:right]
    if patch.size == 0:
        return None
    gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY) if patch.ndim == 3 else patch
    gray = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA)
    return gray.astype(np.float32) / 255.0


def signature_difference(before: np.ndarray, after: np.ndarray) -> float:
    """Return mean absolute difference between two minimap signatures."""
    if before.shape != after.shape:
        return 1.0
    return float(np.mean(np.abs(before - after)))
