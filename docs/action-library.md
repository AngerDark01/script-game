# Composable Action Library

`core.actions` is the device-neutral boundary between a workflow's decision
and the physical or virtual device that carries it out.  It deliberately has
no dependency on OCR, map coordinates, navigation rules, a game, or a GUI.

## Available primitives

| Device | Commands |
| --- | --- |
| Mouse | `MOVE`, `DOUBLE_CLICK` at a validated physical `MappedPoint` |
| Keyboard | `KEY_DOWN`, `KEY_UP`, `KEY_CHORD` |
| Virtual Xbox | `GAMEPAD_BUTTON`, `GAMEPAD_STICK`, `GAMEPAD_TRIGGER`, `GAMEPAD_RESET` |

`ActionRequest` remains available for the existing OCR-to-mouse proof.  New
workflows should emit `ActionCommand` and the appropriate typed target.

## Keyboard composition

The production device is deliberately separate from the adapter, so a
workbench can choose an alternative keyboard backend or use a fake in tests.

```python
from core.actions import (
    ActionCommand,
    ActionKind,
    KeyboardActionAdapter,
    KeyboardTarget,
    PyDirectInputKeyboardDevice,
)

keyboard = KeyboardActionAdapter(device=PyDirectInputKeyboardDevice())
keyboard.execute(ActionCommand(ActionKind.KEY_CHORD, KeyboardTarget(("ctrl", "shift", "p"))))
```

`KEY_DOWN` and `KEY_UP` require exactly one key.  A chord presses keys in the
declared order and releases them in reverse order, including if a later key
fails to press.

## Existing Virtual Xbox host composition

The independent `virtual_gamepad` host/UI remains responsible for elevation,
driver lifecycle, Controller 1/2 start and pause, and its F7/F8/F9 controls.
It must already be running before the following code connects.  This action
library does not start the host, install a driver, or bypass game protections.

```python
from core.actions import (
    ActionCommand,
    ActionKind,
    GamepadButtonTarget,
    GamepadResetTarget,
    GamepadStickTarget,
    VirtualControllerRoute,
    VirtualGamepadActionAdapter,
)

gamepad = VirtualGamepadActionAdapter.connect()
route = VirtualControllerRoute(
    controller=1,
    source="auto_mode.navigation",
    ttl_ms=250,
)

# A steering policy can produce this vector; the adapter only submits it.
gamepad.execute(
    ActionCommand(
        ActionKind.GAMEPAD_STICK,
        GamepadStickTarget(route=route, stick="left", x=0, y=24000),
    )
)

# Button actions use the same selected controller and source.
gamepad.execute(
    ActionCommand(
        ActionKind.GAMEPAD_BUTTON,
        GamepadButtonTarget(route=route, button="a", pressed=True),
    )
)

# Call this on cancellation, failure, or workflow completion.
gamepad.execute(ActionCommand(ActionKind.GAMEPAD_RESET, GamepadResetTarget(route)))
gamepad.close()
```

Every virtual-gamepad target carries an explicit Controller 1/2 route, source,
and positive TTL.  A loop that needs sustained stick, trigger, or button state
must refresh its command before the TTL expires; a cancellation path should
send `GAMEPAD_RESET`.

## Next composition layer

A future steering module may convert `current position + target position` into
`GamepadStickTarget` values.  Velocity estimation, route following, macro
sequences, and the future workbench UI belong above this primitive library and
remain intentionally separate.
