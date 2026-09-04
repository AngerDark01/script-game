# Device-Agnostic Keyboard and Virtual Xbox Actions Design

## Goal

Evolve `core.actions` from its current mapped-pointer proof into a reusable,
device-neutral action library, then add keyboard and Virtual Xbox adapters
without coupling either to OCR, coordinate mapping, navigation, or UI code.

## Context

The existing OCR proof intentionally owns one narrow composition:

```text
MappedPoint(PHYSICAL_SCREEN) + ActionRequest
  -> MouseActionAdapter
  -> ActionResult
```

That remains the correct path for pointer actions. It must remain compatible
with the existing `ActionRequest`, `ActionResult`, and `MouseActionAdapter`
imports used by `workflows.desktop_ocr_action_proof`.

The independent Virtual Gamepad module already owns the privileged Windows
virtual-controller process. Its Python client provides a local named-pipe
interface for controller selection, buttons, sticks, triggers, TTL, and reset.
`auto_modules` must consume that service through a narrow protocol, not import
or duplicate the host implementation.

## Decisions

### 1. Introduce a new generic command contract alongside the legacy request

`core.actions.contracts` will become the primary library surface:

```text
ActionCommand(kind, target)
ActionTarget
ActionResult
ActionAdapter protocol
```

The existing pointer-shaped `ActionRequest` remains as a compatibility DTO for
the current OCR proof. `MouseActionAdapter` will accept both the legacy request
and a generic pointer command, so the existing workflow stays valid while new
workflows use `ActionCommand`.

### 2. Model device-specific payloads as typed targets, not untyped maps

`ActionCommand` carries a device-independent `ActionKind` plus an immutable
typed target. The first target set is:

```text
PointerTarget(mapped_point)
KeyboardTarget(keys)
VirtualControllerRoute(controller, source, ttl_ms)
GamepadButtonTarget(route, button, pressed)
GamepadStickTarget(route, stick, x, y)
GamepadTriggerTarget(route, trigger, value)
```

The target classes validate their own ranges and identifiers. This keeps a
workflow from accidentally sending a mouse coordinate to a gamepad adapter or
a gamepad value outside the Xbox range.

### 3. Keep adapters thin and injectable

```text
ActionCommand
  -> KeyboardActionAdapter -> KeyboardDevice protocol
  -> VirtualGamepadActionAdapter -> VirtualGamepadDevice protocol
```

The keyboard adapter will expose key down, key up, and chord operations.
Production composition can use the project's existing `pydirectinput`
dependency, while all unit tests use a fake keyboard device.

The Xbox adapter will expose button state, stick vectors, trigger values, and
controller reset. It will only depend on a `VirtualGamepadDevice` protocol;
the existing `VirtualGamepadClient` is supplied at composition time. This
preserves the independent elevated host and supports fake devices in tests.

### 4. Treat TTL and reset as safety boundaries

Every gamepad route has an explicit positive TTL. Button, stick, and trigger
commands are scoped to that TTL. A reset command clears the selected virtual
controller. Higher-level loops must refresh commands while they intend to
hold input, and must reset on terminal, cancellation, or localization failure.

This first library slice does not implement navigation-to-stick steering,
velocity estimation, macro sequencing, UI node graphs, or automatic host
startup. Those are later composition-layer modules that will consume these
primitive commands.

### 5. Preserve the current mouse workflow

Pointer mapping remains in `core.spatial`; OCR, recognition, route logic, and
screen geometry remain outside `core.actions`. Existing desktop proof tests
must pass unchanged after the generic contracts are introduced.

## Target Module Shape

```text
core/actions/
  contracts.py       # ActionCommand, ActionTarget variants, ActionResult, protocol
  models.py          # ActionRequest compatibility layer
  mouse.py           # existing concrete pointer adapter
  keyboard.py        # KeyboardActionAdapter and KeyboardDevice protocol
  gamepad.py         # VirtualGamepadActionAdapter and GamepadDevice protocol
  __init__.py        # stable public exports
```

## Composition Examples

```text
OCR -> mapped point -> pointer command -> MouseActionAdapter
decision -> key chord -> KeyboardActionAdapter
navigation policy -> stick vector -> VirtualGamepadActionAdapter
combat policy -> button / trigger -> VirtualGamepadActionAdapter
```

The route planner emits motion goals later; a separate steering policy will
turn those goals into `GamepadStickTarget` commands. It will not be part of
this adapter-library change.

## Verification

Unit tests will prove:

- old mouse requests still execute identically;
- each adapter rejects a target for a different device;
- key-down, key-up, and chord ordering is deterministic;
- button, stick, trigger, controller routing, TTL forwarding, and reset are
  delivered to a fake Virtual Gamepad client;
- invalid axes, trigger values, controller numbers, blank sources, and invalid
  keyboard keys are rejected before device I/O;
- the existing OCR-to-mouse workflow remains green.
