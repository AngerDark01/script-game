from __future__ import annotations

from dataclasses import dataclass

from .relocalization_intent import handle_relocalization_navigation_intent
from .terminal_intent import handle_terminal_navigation_intent


@dataclass(frozen=True)
class NavigationIntentConsumptionResult:
    skip_remaining_frame: bool = False
    terminal_navigation: bool = False


def consume_navigation_intent(
    intent,
    *,
    now_ms: int,
    request_global_relocalization,
    log_event,
    show_relocalizing,
    execute_intent,
    is_manual_event_test_active,
    stop_manual_event_test,
    stop_navigation_tasks,
    disable_game_input_mode,
    reset_auto_navigation_button,
    show_arrived,
    show_failed,
) -> NavigationIntentConsumptionResult:
    """Consume one navigation intent after route overlay refresh."""
    if handle_relocalization_navigation_intent(
        intent,
        request_global_relocalization=request_global_relocalization,
        log_event=log_event,
        show_relocalizing=show_relocalizing,
    ):
        return NavigationIntentConsumptionResult(skip_remaining_frame=True)

    execute_intent(intent, now_ms)

    if intent.metadata.get("terminal") and is_manual_event_test_active():
        stop_manual_event_test(intent.message)

    terminal_navigation = handle_terminal_navigation_intent(
        intent,
        stop_navigation_tasks=stop_navigation_tasks,
        disable_game_input_mode=disable_game_input_mode,
        reset_auto_navigation_button=reset_auto_navigation_button,
        show_arrived=show_arrived,
        show_failed=show_failed,
    )
    return NavigationIntentConsumptionResult(terminal_navigation=terminal_navigation)
