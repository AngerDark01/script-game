from __future__ import annotations

from .formatting import _format_value


def describe_action(action) -> str:
    if action is None:
        return "none"
    action_type = _format_value(getattr(action, "type", "unknown"))
    reason = getattr(action, "reason", "") or ""
    target = getattr(action, "target_global_pos", None)
    screen = getattr(action, "screen_pos", None)
    key = getattr(action, "key", None)
    wait_ms = getattr(action, "wait_ms", None)
    parts = [str(action_type)]
    if target is not None:
        parts.append(f"target={_format_value(target)}")
    if screen is not None:
        parts.append(f"screen={_format_value(screen)}")
    if key is not None:
        parts.append(f"key={key}")
    if wait_ms is not None:
        parts.append(f"wait_ms={wait_ms}")
    if reason:
        parts.append(f"reason={reason}")
    return " ".join(parts)


def describe_task(task) -> str:
    if task is None:
        return "none"
    state = _format_value(getattr(task, "state", "unknown"))
    return (
        f"id={getattr(task, 'id', '?')} event={getattr(task, 'event_type', '?')} "
        f"state={state} pos={_format_value(getattr(task, 'global_pos', None))} "
        f"seen={getattr(task, 'seen_count', '?')} attempts={getattr(task, 'attempts', '?')} "
        f"conf={float(getattr(task, 'confidence', 0.0)):.2f}"
    )
