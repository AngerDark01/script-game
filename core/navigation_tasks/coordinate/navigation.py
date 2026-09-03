from __future__ import annotations

from .formatting import distance, float_point_or_none, registration_fields


def record_navigation_diagnostics(
    diagnostics,
    *,
    now_ms: int,
    task_id: str | None,
    task_kind: str | None,
    target_pos,
    raw_pos,
    trusted_pos,
    control_pos,
    confidence: float,
    route_context,
    arrival_radius: float,
    registration,
) -> None:
    target = float_point_or_none(target_pos)
    raw = float_point_or_none(raw_pos)
    trusted = float_point_or_none(trusted_pos)
    control = float_point_or_none(control_pos)
    if target is None or control is None:
        return

    reg_fields = registration_fields(registration)
    route_projection = route_context.project(control) if route_context is not None else None
    route_deviation = None if route_projection is None else float(route_projection.deviation)
    route_progress = None if route_projection is None else float(route_projection.progress)
    control_to_target = distance(control, target)
    raw_to_target = None if raw is None else distance(raw, target)
    trusted_to_target = None if trusted is None else distance(trusted, target)
    radius = float(arrival_radius)

    if route_deviation is not None and route_deviation >= diagnostics.route_deviation_threshold:
        diagnostics._log_throttled(
            "route projection deviation",
            now_ms,
            key=f"route_deviation:{task_id}",
            task=task_id,
            kind=task_kind,
            target=target,
            raw=raw,
            trusted=trusted,
            control=control,
            confidence=float(confidence or 0.0),
            route_deviation=route_deviation,
            route_progress=route_progress,
            recommend="inspect_route_anchor_or_path_not_relocalization",
            **reg_fields,
        )

    if raw_to_target is not None and raw_to_target <= radius < control_to_target:
        diagnostics._log_throttled(
            "arrival mismatch raw inside control outside",
            now_ms,
            key=f"arrival_mismatch:{task_id}",
            task=task_id,
            kind=task_kind,
            target=target,
            raw=raw,
            trusted=trusted,
            control=control,
            raw_distance=raw_to_target,
            control_distance=control_to_target,
            trusted_distance=trusted_to_target,
            arrival_radius=radius,
            confidence=float(confidence or 0.0),
            recommend="inspect_control_smoothing_or_completion_radius",
            **reg_fields,
        )

    near_limit = radius + diagnostics.target_near_margin
    near_key = str(task_id or "unknown")
    if radius < control_to_target <= near_limit:
        since = diagnostics._near_target_since_ms.setdefault(near_key, int(now_ms))
        if int(now_ms) - since >= diagnostics.target_stall_ms:
            diagnostics._log_throttled(
                "near target not completed",
                now_ms,
                key=f"near_target:{near_key}",
                task=task_id,
                kind=task_kind,
                target=target,
                raw=raw,
                trusted=trusted,
                control=control,
                raw_distance=raw_to_target,
                control_distance=control_to_target,
                trusted_distance=trusted_to_target,
                arrival_radius=radius,
                near_limit=near_limit,
                stalled_ms=int(now_ms) - since,
                confidence=float(confidence or 0.0),
                route_deviation=route_deviation,
                route_progress=route_progress,
                recommend="inspect_arrival_radius_or_movement_not_relocalization",
                **reg_fields,
            )
    else:
        diagnostics._near_target_since_ms.pop(near_key, None)
