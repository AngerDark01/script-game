from __future__ import annotations

import cv2
import numpy as np
from PySide6.QtGui import QImage, QPixmap


def pixmap_from_bgr(image) -> QPixmap | None:
    if image is None:
        return None
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    height, width, channels = rgb.shape
    q_image = QImage(rgb.data, width, height, channels * width, QImage.Format_RGB888)
    return QPixmap.fromImage(q_image.copy())


def unpack_enhanced_map_result(result):
    if isinstance(result, tuple):
        global_map, (crop_x1, crop_y1) = result
        return global_map, crop_x1, crop_y1
    return result, 0, 0


def render_global_map_pixmap(
    *,
    global_map,
    crop_x1: int,
    crop_y1: int,
    nav_path,
    current_position,
    draw_scale: float,
    player_pos=None,
    capture_size=None,
) -> QPixmap | None:
    if global_map.size <= 0:
        return None

    if len(global_map.shape) == 2:
        global_colored = cv2.cvtColor(global_map, cv2.COLOR_GRAY2BGR)
    else:
        global_colored = global_map.copy()

    if nav_path:
        points_to_draw = []
        for px, py in nav_path:
            local_px = px - crop_x1
            local_py = py - crop_y1
            points_to_draw.append([local_px, local_py])
        if len(points_to_draw) > 1:
            cv2.polylines(global_colored, [np.array(points_to_draw)], False, (0, 255, 255), 2)

    current_x, current_y = current_position
    fov_x = int(current_x - crop_x1)
    fov_y = int(current_y - crop_y1)

    if capture_size is not None and player_pos is not None:
        fov_w = int(capture_size[0] * draw_scale)
        fov_h = int(capture_size[1] * draw_scale)
        player_x = int(player_pos[0] * draw_scale)
        player_y = int(player_pos[1] * draw_scale)

        cv2.rectangle(
            global_colored,
            (fov_x - player_x, fov_y - player_y),
            (fov_x - player_x + fov_w, fov_y - player_y + fov_h),
            (0, 255, 0),
            3,
        )

    cv2.circle(global_colored, (fov_x, fov_y), 8, (0, 255, 0), -1)
    cv2.circle(global_colored, (fov_x, fov_y), 10, (0, 0, 255), 2)

    return pixmap_from_bgr(global_colored)

