"""Pure-ish presentation adapter for an in-memory terrain snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import cv2
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QImage, QPixmap, QPainter, QPen, QColor

if TYPE_CHECKING:
    from auto_modules.features.poe2.live_terrain import TerrainSnapshot
    from auto_modules.features.poe2.live_terrain.player_position import PlayerPositionSample
    from auto_modules.features.poe2.live_terrain.orientation import TerrainOrientation


@dataclass(frozen=True)
class TerrainDisplay:
    pixmap: QPixmap
    metadata_lines: tuple[str, ...]


@dataclass(frozen=True)
class LocalizationPresentationState:
    position: tuple[float, float] | None
    trajectory: tuple[tuple[float, float], ...]
    registration: object | None
    candidate_regions: tuple[object, ...]
    registration_version: int
    orientation_status: str


def build_localization_presentation(
    estimate,
    *,
    registration,
    coordinator_registration_version: int,
    trajectory,
    candidates,
) -> LocalizationPresentationState:
    estimate_version = int(getattr(estimate, "registration_version", 0))
    current_version = int(coordinator_registration_version)
    current_registration = (
        registration
        if registration is not None and estimate_version > 0 and estimate_version == current_version
        else None
    )
    return LocalizationPresentationState(
        position=getattr(estimate, "position", None),
        trajectory=tuple(trajectory or ()),
        registration=current_registration,
        candidate_regions=tuple(candidates or ()),
        registration_version=estimate_version,
        orientation_status=(
            "automatic_calibration_confirmed"
            if current_registration is not None
            else "waiting_for_automatic_calibration"
        ),
    )




def terrain_pixmap(snapshot: TerrainSnapshot, orientation: "TerrainOrientation | None" = None) -> QPixmap:
    """Render the live grid in the established stitched-map visual style.

    The producer's ``cell_state`` is a terrain classification, while the old
    visual map uses a dark explored surface and bright wall pixels. Unknown
    cells remain black so they cannot be mistaken for captured geometry.
    """
    if orientation is not None:
        cell_state = orientation.transform_array(snapshot.cell_state)
        known_mask = orientation.transform_array(snapshot.known_mask)
    else:
        cell_state = snapshot.cell_state
        known_mask = snapshot.known_mask
    height, width = cell_state.shape
    rgb = np.empty((height, width, 3), dtype=np.uint8)
    rgb[:, :] = (0, 0, 0)
    walkable = (cell_state == 1) & (known_mask > 0)
    rgb[walkable] = (60, 60, 60)

    # The producer classifies the complete rectangular buffer, including the
    # blocked space outside rooms. Derive the legacy white wall look from the
    # boundary of walkable cells instead of painting every blocked cell white.
    walkable_padded = np.pad(walkable, 1, mode="constant", constant_values=False)
    kernel = np.ones((3, 3), dtype=np.uint8)
    dilated = cv2.dilate(walkable_padded.astype(np.uint8), kernel)[1:-1, 1:-1] > 0
    eroded = cv2.erode(walkable_padded.astype(np.uint8), kernel)[1:-1, 1:-1] > 0
    edge = dilated & ~eroded
    rgb[edge] = (235, 235, 235)
    image = QImage(
        rgb.data,
        width,
        height,
        width * 3,
        QImage.Format_RGB888,
    ).copy()
    return QPixmap.fromImage(image)


def present_snapshot(
    snapshot: TerrainSnapshot,
    orientation: "TerrainOrientation | None" = None,
    player_position: "PlayerPositionSample | None" = None,
) -> TerrainDisplay:
    metadata = snapshot.metadata
    pixmap = terrain_pixmap(snapshot, orientation)
    if player_position is not None:
        pixmap = present_player_position_overlay(
            pixmap,
            player_position,
            source_shape=(metadata.height, metadata.width),
            orientation=orientation,
        )
    position_line = (
        f"人物网格位置：{player_position.grid[0]:.2f}，{player_position.grid[1]:.2f}"
        if player_position is not None
        else "人物网格位置：未读取"
    )
    return TerrainDisplay(
        pixmap=pixmap,
        metadata_lines=(
            f"区域：{metadata.area_id}",
            f"实例：{metadata.instance_id}",
            f"尺寸：{metadata.width} × {metadata.height}",
            f"抓取：{metadata.captured_at}",
            f"完整性：{metadata.raw_sha256 or '已通过结构校验'}",
            "方向：等待自动校准（native）",
            position_line,
        ),
    )


def present_player_position_overlay(
    base_pixmap: QPixmap,
    player_position: "PlayerPositionSample",
    *,
    source_shape: tuple[int, int],
    orientation: "TerrainOrientation | None" = None,
) -> QPixmap:
    """Draw one memory-derived player position on a terrain pixmap."""
    if base_pixmap is None or base_pixmap.isNull():
        return QPixmap()
    point = player_position.grid
    if orientation is not None:
        point = orientation.transform_point(point, source_shape)
    x, y = float(point[0]), float(point[1])
    if not (0.0 <= x < base_pixmap.width() and 0.0 <= y < base_pixmap.height()):
        return QPixmap(base_pixmap)
    result = QPixmap(base_pixmap)
    painter = QPainter(result)
    try:
        radius = max(4, min(result.width(), result.height()) // 140)
        painter.setPen(QPen(QColor(20, 230, 120), max(2, radius // 3)))
        painter.setBrush(QColor(20, 230, 120, 180))
        painter.drawEllipse(QPointF(x, y), radius, radius)
        painter.setPen(QPen(QColor(255, 255, 255), max(1, radius // 4)))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPointF(x, y), radius + 2, radius + 2)
    finally:
        painter.end()
    return result


def present_localization_overlay(base_pixmap: QPixmap, state) -> QPixmap:
    """Draw runtime evidence, then apply the matched map direction.

    The registrar transforms the minimap feature into native-map coordinates.
    Therefore the inverse rotation (and the same horizontal reflection) maps
    the native terrain back into the game's minimap orientation for display.
    The transformation is applied after drawing the overlay so the trail and
    current point stay in exactly the same coordinate system as the map.
    """
    if base_pixmap is None or base_pixmap.isNull():
        return QPixmap()
    result = QPixmap(base_pixmap)
    painter = QPainter(result)
    try:
        candidates = tuple(getattr(state, "candidate_regions", ()) or ())
        if candidates:
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(70, 170, 255, 190), max(1, result.width() // 1400), Qt.DashLine))
            for candidate in candidates:
                point = getattr(candidate, "position", None)
                if point is None:
                    continue
                radius_x = radius_y = max(7.0, min(result.width(), result.height()) / 220.0)
                covariance = getattr(candidate, "covariance", None)
                if covariance is not None:
                    values = np.linalg.eigvalsh(np.asarray(covariance, dtype=np.float64))
                    radius_x = max(radius_x, 2.0 * float(np.sqrt(max(values[-1], 0.0))))
                    radius_y = max(radius_y, 2.0 * float(np.sqrt(max(values[0], 0.0))))
                painter.drawEllipse(QPointF(float(point[0]), float(point[1])), radius_x, radius_y)
        trail = tuple(getattr(state, "trajectory", ()) or ())
        if len(trail) >= 2:
            painter.setPen(QPen(QColor(255, 196, 0), max(2, result.width() // 1200)))
            for first, second in zip(trail, trail[1:]):
                painter.drawLine(QPointF(float(first[0]), float(first[1])), QPointF(float(second[0]), float(second[1])))
        position = getattr(state, "position", None)
        if position is not None:
            painter.setPen(QPen(QColor(20, 230, 120), max(2, result.width() // 900)))
            radius = max(9, min(result.width(), result.height()) // 180)
            painter.setBrush(QColor(20, 230, 120, 180))
            painter.drawEllipse(QPointF(float(position[0]), float(position[1])), radius, radius)
    finally:
        painter.end()
    registration = getattr(state, "registration", None)
    transform = getattr(registration, "transform", None)
    if transform is None:
        return result
    return _apply_inverse_registration_transform(result, transform)


def prepare_localization_map(base_pixmap: QPixmap, transform=None) -> QPixmap:
    """Create the direction-corrected base map once for repeated overlays."""
    if base_pixmap is None or base_pixmap.isNull():
        return QPixmap()
    if transform is None:
        return QPixmap(base_pixmap)
    return _apply_inverse_registration_transform(base_pixmap, transform)


def present_registered_overlay(base_pixmap: QPixmap, state, *, source_size, transform=None) -> QPixmap:
    """Draw a localization overlay on a map already transformed for display.

    Unlike ``present_localization_overlay()``, this function never rotates the
    map. It maps only the small set of marker/trail points into display space.
    """
    if base_pixmap is None or base_pixmap.isNull():
        return QPixmap()
    result = QPixmap(base_pixmap)
    painter = QPainter(result)
    map_point = lambda point: localization_display_point(
        point,
        source_size=source_size,
        transform=transform,
    )
    try:
        candidates = tuple(getattr(state, "candidate_regions", ()) or ())
        if candidates:
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(70, 170, 255, 190), max(1, result.width() // 1400), Qt.DashLine))
            for candidate in candidates:
                point = getattr(candidate, "position", None)
                if point is not None:
                    x, y = map_point(point)
                    radius = max(7.0, min(result.width(), result.height()) / 220.0)
                    painter.drawEllipse(QPointF(x, y), radius, radius)
        trail = tuple(getattr(state, "trajectory", ()) or ())
        if len(trail) >= 2:
            painter.setPen(QPen(QColor(255, 196, 0), max(2, result.width() // 1200)))
            for first, second in zip(trail, trail[1:]):
                first_x, first_y = map_point(first)
                second_x, second_y = map_point(second)
                painter.drawLine(QPointF(first_x, first_y), QPointF(second_x, second_y))
        position = getattr(state, "position", None)
        if position is not None:
            x, y = map_point(position)
            painter.setPen(QPen(QColor(20, 230, 120), max(2, result.width() // 900)))
            painter.setBrush(QColor(20, 230, 120, 180))
            radius = max(9, min(result.width(), result.height()) // 180)
            painter.drawEllipse(QPointF(x, y), radius, radius)
    finally:
        painter.end()
    return result


def localization_display_point(point, *, source_size: tuple[int, int], transform=None) -> tuple[float, float]:
    """Map a localization point to the displayed overlay pixmap coordinates."""
    x, y = float(point[0]), float(point[1])
    if transform is None:
        return x, y
    angle = float(getattr(transform, "angle_degrees", 0.0))
    reflected = bool(getattr(transform, "reflect_horizontal", False))
    width, height = int(source_size[0]), int(source_size[1])
    if abs(angle) > 1e-3:
        center = (width / 2.0, height / 2.0)
        matrix = cv2.getRotationMatrix2D(center, -angle, 1.0)
        cos_value = abs(float(matrix[0, 0]))
        sin_value = abs(float(matrix[0, 1]))
        bound_width = max(1, int(round(height * sin_value + width * cos_value)))
        bound_height = max(1, int(round(height * cos_value + width * sin_value)))
        matrix[0, 2] += bound_width / 2.0 - center[0]
        matrix[1, 2] += bound_height / 2.0 - center[1]
        mapped = matrix @ np.array([x, y, 1.0], dtype=np.float64)
        x, y = float(mapped[0]), float(mapped[1])
        width, height = bound_width, bound_height
    if reflected:
        x = float(width - 1) - x
    return x, y


def _pixmap_rgb_array(pixmap: QPixmap) -> np.ndarray:
    image = pixmap.toImage().convertToFormat(QImage.Format_RGBA8888)
    size = image.sizeInBytes()
    buffer = np.frombuffer(image.bits(), dtype=np.uint8, count=size)
    rows = buffer.reshape((image.height(), image.bytesPerLine() // 4, 4))
    return np.array(rows[:, : image.width(), :3], copy=True)


def _apply_inverse_registration_transform(pixmap: QPixmap, transform) -> QPixmap:
    """Return a display copy in minimap orientation for any matched angle."""
    array = _pixmap_rgb_array(pixmap)
    angle = float(getattr(transform, "angle_degrees", 0.0))
    reflected = bool(getattr(transform, "reflect_horizontal", False))
    if abs(angle) > 1e-3:
        height, width = array.shape[:2]
        center = (width / 2.0, height / 2.0)
        matrix = cv2.getRotationMatrix2D(center, -angle, 1.0)
        cos_value = abs(matrix[0, 0])
        sin_value = abs(matrix[0, 1])
        bound_width = max(1, int(round(height * sin_value + width * cos_value)))
        bound_height = max(1, int(round(height * cos_value + width * sin_value)))
        matrix[0, 2] += bound_width / 2.0 - center[0]
        matrix[1, 2] += bound_height / 2.0 - center[1]
        array = cv2.warpAffine(
            array,
            matrix,
            (bound_width, bound_height),
            flags=cv2.INTER_NEAREST,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0),
        )
    if reflected:
        array = np.fliplr(array)
    height, width = array.shape[:2]
    image = QImage(
        np.ascontiguousarray(array).data,
        width,
        height,
        width * 3,
        QImage.Format_RGB888,
    ).copy()
    return QPixmap.fromImage(image)


def frame_pixmap(frame) -> QPixmap:
    """Convert a BGR/gray numpy frame to a detached Qt pixmap."""
    if frame is None:
        return QPixmap()
    if isinstance(frame, QPixmap):
        return QPixmap(frame)
    if hasattr(frame, "toImage"):
        return QPixmap.fromImage(frame.toImage())
    array = np.asarray(frame)
    if array.size == 0 or array.ndim not in (2, 3):
        return QPixmap()
    if array.ndim == 2:
        image = QImage(array.data, array.shape[1], array.shape[0], array.strides[0], QImage.Format_Grayscale8)
    elif array.shape[2] == 4:
        image = QImage(array.data, array.shape[1], array.shape[0], array.strides[0], QImage.Format_RGBA8888)
    else:
        image = QImage(array.data, array.shape[1], array.shape[0], array.strides[0], QImage.Format_BGR888)
    return QPixmap.fromImage(image.copy())
