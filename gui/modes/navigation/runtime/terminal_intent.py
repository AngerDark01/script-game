from __future__ import annotations

from core.navigation_tasks.models import NavigationIntentType


def handle_terminal_navigation_intent(
    intent,
    *,
    stop_navigation_tasks,
    disable_game_input_mode,
    reset_auto_navigation_button,
    show_arrived,
    show_failed,
) -> bool:
    """Handle ARRIVED/FAILED navigation intents and report whether it was terminal."""
    if intent.type not in (NavigationIntentType.ARRIVED, NavigationIntentType.FAILED):
        return False

    stop_navigation_tasks()
    disable_game_input_mode()
    reset_auto_navigation_button()

    if intent.type == NavigationIntentType.ARRIVED:
        show_arrived()
    else:
        show_failed(intent.message)
    return True
