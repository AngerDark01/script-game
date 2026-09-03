from __future__ import annotations


def handle_relocalization_navigation_intent(
    intent,
    *,
    request_global_relocalization,
    log_event,
    show_relocalizing,
) -> bool:
    """Handle force-relocalize intents and report whether the frame was consumed."""
    if not intent.metadata.get("force_relocalize"):
        return False

    reason = intent.metadata.get("relocalize_reason") or "coordinate_recovery"
    request_global_relocalization(reason)
    log_event(
        "navigation forced global relocalization",
        reason=reason,
        score=intent.metadata.get("relocalize_score"),
        player=intent.player_pos,
        task=intent.task_id,
    )
    show_relocalizing()
    return True
