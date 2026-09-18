from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from auto_modules.adapters.input import MotionControllerActionAdapter

from .actions import MapMovementAction, PrimitiveNavigationAction, translate_navigation_intent


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
    action_adapter=None,
) -> NavigationIntentExecutionResult:
    """Execute a typed navigation composition action through compatibility backends."""
    action = translate_navigation_intent(intent)
    if action is None:
        return NavigationIntentExecutionResult()

    if isinstance(action, MapMovementAction):
        enable_game_input_mode()
        motion_controller.set_control_enabled(True)
        if action.force_click_target:
            click_info = motion_controller.click_map_target_once(
                action.player_position,
                action.target_position,
                reason=intent.message or "navigation_forced_target",
            )
        else:
            click_info = motion_controller.move_to_map_target(
                action.player_position,
                action.target_position,
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

    if isinstance(action, PrimitiveNavigationAction):
        enable_game_input_mode()
        (action_adapter or MotionControllerActionAdapter(controller=motion_controller)).execute(
            action.command,
            reason=action.reason,
        )
        return NavigationIntentExecutionResult(handled=True)

    return NavigationIntentExecutionResult()
