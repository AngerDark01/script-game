from __future__ import annotations

from PySide6.QtGui import QBrush, QColor, QPainterPath, QPen

from .event_overlay import global_to_scene


def clear_route_overlay(scene, items: list) -> tuple[list, object | None]:
    for item in items:
        try:
            scene.removeItem(item)
        except RuntimeError:
            pass
    return [], None


def render_route_overlay(
    scene,
    nav_core,
    route_data,
    items: list,
    current_path=None,
    current_subgoal=None,
    current_required_index=None,
    current_guide_index=None,
    current_target_kind=None,
) -> tuple[list, object | None]:
    if not scene or not nav_core:
        return items, None

    items, route_path_item = clear_route_overlay(scene, items)
    main = (route_data or {}).get("routes", {}).get("main", {})
    exit_region = main.get("exit_region")
    required_points = main.get("required_points", [])
    guide_points = main.get("guide_points", [])

    if exit_region:
        center = global_to_scene(exit_region["center"], nav_core)
        if center:
            radius = exit_region["radius"]
            item = scene.addEllipse(
                center[0] - radius,
                center[1] - radius,
                radius * 2,
                radius * 2,
                QPen(QColor(255, 170, 0), 2),
            )
            item.setZValue(3)
            items.append(item)

    required_pending = (
        current_required_index is not None
        and current_required_index < len(required_points)
    )
    for index, point in enumerate(required_points, start=1):
        mapped = global_to_scene(point, nav_core)
        if mapped is None:
            continue
        is_completed = current_required_index is not None and (index - 1) < current_required_index
        is_current = (
            current_target_kind == "required"
            and required_pending
            and (index - 1) == current_required_index
        )
        color = QColor(176, 84, 255) if not is_completed else QColor(130, 130, 130)
        pen_width = 3 if is_current else 2
        radius = 6 if is_current else 5
        ellipse = scene.addEllipse(
            mapped[0] - radius,
            mapped[1] - radius,
            radius * 2,
            radius * 2,
            QPen(color, pen_width),
            QBrush(color),
        )
        ellipse.setZValue(4)
        items.append(ellipse)
        text = scene.addText(f"R{index}")
        text.setDefaultTextColor(color)
        text.setPos(mapped[0] + 8, mapped[1] - 12)
        text.setZValue(4)
        items.append(text)

    for index, point in enumerate(guide_points, start=1):
        mapped = global_to_scene(point, nav_core)
        if mapped is None:
            continue
        color = QColor(0, 200, 255)
        pen_width = 2
        radius = 4
        ellipse = scene.addEllipse(
            mapped[0] - radius,
            mapped[1] - radius,
            radius * 2,
            radius * 2,
            QPen(color, pen_width),
            QBrush(color),
        )
        ellipse.setZValue(4)
        items.append(ellipse)
        text = scene.addText(f"A{index}")
        text.setDefaultTextColor(color)
        text.setPos(mapped[0] + 6, mapped[1] - 10)
        text.setZValue(4)
        items.append(text)

    if current_path:
        path = QPainterPath()
        first = global_to_scene(current_path[0], nav_core)
        if first:
            path.moveTo(first[0], first[1])
            for point in current_path[1:]:
                mapped = global_to_scene(point, nav_core)
                if mapped:
                    path.lineTo(mapped[0], mapped[1])
            route_path_item = scene.addPath(
                path,
                QPen(QColor(255, 255, 0, 180), 2),
            )
            route_path_item.setZValue(3)
            items.append(route_path_item)

    if current_subgoal:
        mapped = global_to_scene(current_subgoal, nav_core)
        if mapped:
            subgoal = scene.addEllipse(
                mapped[0] - 5,
                mapped[1] - 5,
                10,
                10,
                QPen(QColor(255, 0, 255), 2),
                QBrush(QColor(255, 0, 255)),
            )
            subgoal.setZValue(5)
            items.append(subgoal)

    return items, route_path_item
