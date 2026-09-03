"""Navigation input adapters."""

from .intent_executor import NavigationIntentExecutionResult, execute_navigation_intent
from .window_mode import GameInputWindowMode

__all__ = [
    "GameInputWindowMode",
    "NavigationIntentExecutionResult",
    "execute_navigation_intent",
]
