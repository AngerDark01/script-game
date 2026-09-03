from __future__ import annotations

import math

from core.events.debug import event_log

from .environment_signature import minimap_environment_signature, signature_difference


def detect_teleport_completion(*, config, event_type: str, entry_task, tick, interact_pos, interact_signature) -> dict | None:
    """Detect whether a portal interaction has completed teleportation."""
    if interact_pos is not None and tick.player_global_pos is not None:
        distance = math.hypot(
            float(tick.player_global_pos[0]) - float(interact_pos[0]),
            float(tick.player_global_pos[1]) - float(interact_pos[1]),
        )
        exit_task, exit_distance = near_known_exit_portal(
            config=config,
            event_type=event_type,
            entry_task=entry_task,
            tick=tick,
        )
        if exit_task is not None:
            event_log(
                "portal teleport known exit reached",
                exit_id=getattr(exit_task, "id", None),
                exit_pos=getattr(exit_task, "global_pos", None),
                distance=float(distance),
                exit_distance=float(exit_distance),
                radius=int(config.exit_complete_radius),
            )
            return {
                "completion_reason": "known_exit",
                "exit_task_id": getattr(exit_task, "id", None),
                "exit_pos": getattr(exit_task, "global_pos", None),
                "exit_player_pos": _int_pos(tick.player_global_pos),
            }

        if distance >= float(config.teleport_min_distance):
            event_log(
                "portal teleport position changed",
                distance=float(distance),
                threshold=int(config.teleport_min_distance),
            )
            return {
                "completion_reason": "position_changed",
                "exit_pos": _int_pos(tick.player_global_pos),
                "exit_player_pos": _int_pos(tick.player_global_pos),
            }

    current_signature = minimap_environment_signature(tick.raw_minimap_frame, tick.player_local_minimap_pos)
    if interact_signature is not None and current_signature is not None:
        diff = signature_difference(interact_signature, current_signature)
        if diff >= float(config.environment_change_threshold):
            event_log(
                "portal teleport environment changed",
                diff=float(diff),
                threshold=float(config.environment_change_threshold),
            )
            return {
                "completion_reason": "environment_changed",
                "exit_pos": _int_pos(tick.player_global_pos),
                "exit_player_pos": _int_pos(tick.player_global_pos),
            }
    return None


def near_known_exit_portal(*, config, event_type: str, entry_task, tick):
    """Find a nearby non-completed portal task that can represent the teleport exit."""
    if tick.player_global_pos is None:
        return None, 0.0
    radius = float(getattr(config, "exit_complete_radius", 120))
    best_task = None
    best_distance = None
    for task in getattr(tick, "event_tasks", []) or []:
        if getattr(task, "event_type", None) != event_type:
            continue
        if entry_task is not None and task is entry_task:
            continue
        state_value = getattr(getattr(task, "state", None), "value", getattr(task, "state", None))
        if str(state_value).lower() in {"completed", "ignored"}:
            continue
        global_pos = getattr(task, "global_pos", None)
        if global_pos is None:
            continue
        distance = math.hypot(
            float(global_pos[0]) - float(tick.player_global_pos[0]),
            float(global_pos[1]) - float(tick.player_global_pos[1]),
        )
        entry_distance = None
        if entry_task is not None and getattr(entry_task, "global_pos", None) is not None:
            entry_distance = math.hypot(
                float(entry_task.global_pos[0]) - float(tick.player_global_pos[0]),
                float(entry_task.global_pos[1]) - float(tick.player_global_pos[1]),
            )
        if entry_distance is not None and distance >= entry_distance:
            continue
        if distance <= radius and (best_distance is None or distance < best_distance):
            best_task = task
            best_distance = distance
    return best_task, float(best_distance or 0.0)


def _int_pos(pos) -> tuple[int, int] | None:
    if pos is None:
        return None
    return (int(pos[0]), int(pos[1]))
