from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from core.navigation_tasks.models import NavigationIntentType


@dataclass(frozen=True)
class NavigationIntentExecutionResult:
    handled: bool = False
    status_suffix: str | None = None


def execute_navigation_intent(
    intent,
    now_ms: int,
    *,
    motion_controller,
    navigation_task_controller,
    enable_game_input_mode: Callable[[], None],
) -> NavigationIntentExecutionResult:
    """Execute a navigation intent against the GUI-owned input adapter."""
    if intent is None or intent.type in (NavigationIntentType.NONE, NavigationIntentType.WAIT):
        return NavigationIntentExecutionResult()

    if intent.type == NavigationIntentType.MOVE_MAP:
        if not intent.player_pos or not intent.subgoal:
            return NavigationIntentExecutionResult()
        enable_game_input_mode()
        motion_controller.set_control_enabled(True)
        if intent.metadata.get("force_click_target"):
            click_info = motion_controller.click_map_target_once(
                intent.player_pos,
                intent.subgoal,
                reason=intent.message or "navigation_forced_target",
            )
        else:
            click_info = motion_controller.move_to_map_target(
                intent.player_pos,
                intent.subgoal,
            )
        if click_info:
            navigation_task_controller.record_intent_click(intent, now_ms)
            return NavigationIntentExecutionResult(
                handled=True,
                status_suffix=(
                    f"click r:{click_info['screen_radius']:.0f}/"
                    f"raw:{click_info.get('raw_screen_radius', 0):.0f}"
                ),
            )
        return NavigationIntentExecutionResult(handled=True)

    if intent.type == NavigationIntentType.CLICK_SCREEN:
        screen_pos = intent.metadata.get("screen_pos")
        if screen_pos:
            enable_game_input_mode()
            motion_controller.click_screen_position(
                screen_pos,
                reason=intent.message or "navigation_event_click",
            )
            return NavigationIntentExecutionResult(handled=True)
        return NavigationIntentExecutionResult()

    if intent.type == NavigationIntentType.PRESS_KEY:
        key = intent.metadata.get("key")
        if key:
            enable_game_input_mode()
            motion_controller.press_key(key, reason=intent.message or "navigation_event_key")
            return NavigationIntentExecutionResult(handled=True)
        return NavigationIntentExecutionResult()

    return NavigationIntentExecutionResult()
