"""Device-agnostic action requests and concrete input adapters."""

from .models import ActionKind, ActionRequest, ActionResult
from .mouse import ActionExecutionError, MouseActionAdapter, MouseDevice

__all__ = [
    "ActionExecutionError",
    "ActionKind",
    "ActionRequest",
    "ActionResult",
    "MouseActionAdapter",
    "MouseDevice",
]
