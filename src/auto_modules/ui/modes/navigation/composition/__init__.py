"""Navigation composition helpers."""

from .lifecycles import (
    initialize_navigation_pre_signal_lifecycles,
    initialize_navigation_runtime_lifecycles,
)

__all__ = [
    "initialize_navigation_pre_signal_lifecycles",
    "initialize_navigation_runtime_lifecycles",
]
