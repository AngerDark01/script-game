"""Python adapter for the virtual-gamepad Host protocol."""

from .virtual_gamepad_client import (
    JsonFileTransport,
    PIPE_PATH,
    VirtualGamepadClient,
    VirtualGamepadError,
)
from auto_modules.core.actions.gamepad import VirtualGamepadActionAdapter
from .program_output import ProgramGamepadOutput, host_clock_ms


def connect_action_adapter(
    *, timeout: float = 5.0, device_id: str = "virtual_gamepad"
) -> VirtualGamepadActionAdapter:
    """Connect the generic action adapter to the concrete Host client."""
    client = VirtualGamepadClient()
    client.connect(timeout=timeout)
    return VirtualGamepadActionAdapter(device=client, device_id=device_id)

__all__ = [
    "JsonFileTransport",
    "PIPE_PATH",
    "ProgramGamepadOutput",
    "VirtualGamepadClient",
    "VirtualGamepadError",
    "connect_action_adapter",
    "host_clock_ms",
]
