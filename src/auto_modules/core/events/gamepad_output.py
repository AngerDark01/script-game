"""Translate declarative event inputs into one neutral-safe XInput state."""
from __future__ import annotations

from math import hypot


BUTTON_MASKS = {
    "A": 0x1000, "B": 0x2000, "X": 0x4000, "Y": 0x8000,
    "LB": 0x100, "RB": 0x200, "BACK": 0x20, "START": 0x10,
    "LS": 0x40, "RS": 0x80, "UP": 1, "DOWN": 2, "LEFT": 4, "RIGHT": 8,
}

# Positive X is right and positive Y is up in XInput.
LEFT_STICK_INPUTS = {
    "LS_UP": (0, 1),
    "LS_DOWN": (0, -1),
    "LS_LEFT": (-1, 0),
    "LS_RIGHT": (1, 0),
    "LS_UP_LEFT": (-1, 1),
    "LS_UP_RIGHT": (1, 1),
    "LS_DOWN_LEFT": (-1, -1),
    "LS_DOWN_RIGHT": (1, -1),
}

EVENT_INPUTS = tuple(BUTTON_MASKS) + tuple(LEFT_STICK_INPUTS)


def state_from_inputs(inputs) -> dict:
    """Merge buttons and movement directions into a complete host state."""
    buttons = 0
    x = y = 0
    for name in set(inputs):
        buttons |= BUTTON_MASKS.get(name, 0)
        dx, dy = LEFT_STICK_INPUTS.get(name, (0, 0))
        x += dx
        y += dy
    length = hypot(x, y)
    if length:
        x = round(x / length * 32767)
        y = round(y / length * 32767)
    return {
        "buttons": buttons,
        "leftTrigger": 0,
        "rightTrigger": 0,
        "leftStickX": x,
        "leftStickY": y,
        "rightStickX": 0,
        "rightStickY": 0,
    }
