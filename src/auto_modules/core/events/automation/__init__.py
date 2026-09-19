"""Generic event automation runtimes.

The package contains domain-neutral, bounded runtimes that turn declarative
steps into event actions. Game features may wrap these runtimes with their own
configuration and policies.
"""

from .action_sequence import (
    ActionSequenceDefinition,
    ActionSequenceHandler,
    BUTTONS,
    button_mask,
    inputs_mask,
)
from .definitions import (
    EventDefinitionRepository,
    ExecutableEventDefinition,
    parse_event_definition,
)
from .execution import EventExecutionRuntime, EventStateFrame
from .routes import EventDispatch, EventRoute, EventRouteRepository, EventRouter

__all__ = [
    "EventDefinitionRepository",
    "ExecutableEventDefinition",
    "parse_event_definition",
    "EventDispatch",
    "EventRoute",
    "EventRouteRepository",
    "EventRouter",
    "EventExecutionRuntime",
    "EventStateFrame",
    "ActionSequenceDefinition",
    "ActionSequenceHandler",
    "BUTTONS",
    "button_mask",
    "inputs_mask",
]
