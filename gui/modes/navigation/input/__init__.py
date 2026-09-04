"""Navigation input adapters."""

from .actions import MapMovementAction, PrimitiveNavigationAction, translate_navigation_intent
from .intent_executor import NavigationIntentExecutionResult, execute_navigation_intent
from .window_mode import GameInputWindowMode

__all__ = [
    "GameInputWindowMode",
    "MapMovementAction",
    "NavigationIntentExecutionResult",
    "PrimitiveNavigationAction",
    "execute_navigation_intent",
    "translate_navigation_intent",
]
