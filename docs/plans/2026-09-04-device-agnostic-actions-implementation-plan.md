# Device-Agnostic Keyboard and Virtual Xbox Actions — Implementation Plan

## Goal

Add tested keyboard and Virtual Xbox primitive action adapters to
`core.actions`, while retaining the current mapped-pointer mouse workflow.

## Architecture Overview

`ActionCommand` and typed `ActionTarget` values are the new device-neutral
contract. The existing `ActionRequest` is retained as a compatibility DTO for
the completed OCR-to-mouse proof. Mouse, keyboard, and gamepad adapters each
accept only their own target types and rely on injected device protocols.

The Xbox adapter receives an injected client compatible with the independent
Virtual Gamepad Python client. It does not start a host, install a driver, or
know routes, OCR, UI, navigation, or game-specific policy.

## Tech Stack

- Python 3.12
- Standard-library `dataclasses`, `typing.Protocol`, and `unittest`
- Existing `pydirectinput` dependency for production keyboard composition
- Existing independent Virtual Gamepad named-pipe client, injected by callers

## Task 1: Add generic action contracts and validation

**Files**

- Add `core/actions/contracts.py`
- Add `tests/test_action_contracts.py`

**Test first**

```python
def test_gamepad_stick_target_rejects_out_of_range_axis_values(self):
    route = VirtualControllerRoute(controller=1, source="test", ttl_ms=250)
    with self.assertRaises(ValueError):
        GamepadStickTarget(route=route, stick="left", x=32768, y=0)

def test_command_requires_compatible_kind_and_target(self):
    target = KeyboardTarget(("ctrl", "s"))
    with self.assertRaises(ValueError):
        ActionCommand(ActionKind.GAMEPAD_STICK, target)
```

**Verify red**

```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_action_contracts
# Expected: ImportError / missing contract types before implementation.
```

**Implementation contract**

```python
class ActionKind(StrEnum):
    MOVE = "move"
    DOUBLE_CLICK = "double_click"
    KEY_DOWN = "key_down"
    KEY_UP = "key_up"
    KEY_CHORD = "key_chord"
    GAMEPAD_BUTTON = "gamepad_button"
    GAMEPAD_STICK = "gamepad_stick"
    GAMEPAD_TRIGGER = "gamepad_trigger"
    GAMEPAD_RESET = "gamepad_reset"

@dataclass(frozen=True)
class VirtualControllerRoute:
    controller: int = 1
    source: str = "actions"
    ttl_ms: int = 250

@dataclass(frozen=True)
class KeyboardTarget(ActionTarget):
    keys: tuple[str, ...]

@dataclass(frozen=True)
class GamepadStickTarget(ActionTarget):
    route: VirtualControllerRoute
    stick: str
    x: int
    y: int

@dataclass(frozen=True)
class ActionCommand:
    kind: ActionKind
    target: ActionTarget
```

Implement immutable `PointerTarget`, `KeyboardTarget`,
`GamepadButtonTarget`, `GamepadStickTarget`, `GamepadTriggerTarget`, and
`GamepadResetTarget` variants. Validate controller range `1..2`, nonempty
source/key/button, stick values in `[-32768, 32767]`, trigger values in
`[0, 255]`, and compatible `kind`/target pairs. Define the common
`ActionAdapter` protocol and make `ActionResult.point` optional so non-pointer
commands can report results without fabricated coordinates.

**Verify green**

```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_action_contracts
# Expected: all contract validation tests pass.
```

**Commit**

```text
feat: add device-agnostic action contracts
```

## Task 2: Add keyboard action adapter

**Files**

- Add `core/actions/keyboard.py`
- Add `tests/test_keyboard_action_adapter.py`

**Test first**

```python
def test_key_chord_presses_in_order_and_releases_in_reverse_order(self):
    device = FakeKeyboardDevice()
    command = ActionCommand(ActionKind.KEY_CHORD, KeyboardTarget(("ctrl", "shift", "p")))

    result = KeyboardActionAdapter(device=device, clock_ms=lambda: 10).execute(command)

    self.assertEqual(
        [("down", "ctrl"), ("down", "shift"), ("down", "p"),
         ("up", "p"), ("up", "shift"), ("up", "ctrl")],
        device.calls,
    )
    self.assertTrue(result.executed)
```

**Verify red**

```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_keyboard_action_adapter
# Expected: ImportError for KeyboardActionAdapter before implementation.
```

**Implementation contract**

```python
class KeyboardDevice(Protocol):
    def key_down(self, key: str) -> None: ...
    def key_up(self, key: str) -> None: ...

class KeyboardActionAdapter:
    def execute(self, command: ActionCommand) -> ActionResult:
        if command.kind is ActionKind.KEY_DOWN:
            self._device.key_down(command.target.keys[0])
        elif command.kind is ActionKind.KEY_UP:
            self._device.key_up(command.target.keys[0])
        elif command.kind is ActionKind.KEY_CHORD:
            for key in command.target.keys:
                self._device.key_down(key)
            for key in reversed(command.target.keys):
                self._device.key_up(key)
        else:
            raise ValueError(...)
```

Use a small production `PyDirectInputKeyboardDevice` wrapper, but keep
`pydirectinput` imported only in that concrete wrapper. Verify foreign targets
are rejected before a fake device records any call.

**Verify green**

```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_keyboard_action_adapter
# Expected: key down, key up, chord ordering, and rejection tests pass.
```

**Commit**

```text
feat: add reusable keyboard action adapter
```

## Task 3: Add Virtual Xbox action adapter

**Files**

- Add `core/actions/gamepad.py`
- Add `tests/test_gamepad_action_adapter.py`

**Test first**

```python
def test_stick_command_routes_both_axes_and_ttl_to_selected_controller(self):
    client = FakeGamepadDevice()
    route = VirtualControllerRoute(controller=2, source="nav", ttl_ms=300)
    command = ActionCommand(
        ActionKind.GAMEPAD_STICK,
        GamepadStickTarget(route=route, stick="left", x=-12000, y=22000),
    )

    VirtualGamepadActionAdapter(device=client, clock_ms=lambda: 20).execute(command)

    self.assertEqual(
        [("set_axis", "left_x", -12000, "nav", 300, 2),
         ("set_axis", "left_y", 22000, "nav", 300, 2)],
        client.calls,
    )
```

**Verify red**

```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_gamepad_action_adapter
# Expected: ImportError for VirtualGamepadActionAdapter before implementation.
```

**Implementation contract**

```python
class VirtualGamepadDevice(Protocol):
    def button(self, button: str, action: str, source: str, ttl_ms: int | None, controller: int) -> None: ...
    def set_axis(self, axis: str, value: int, source: str, ttl_ms: int | None, controller: int) -> None: ...
    def set_trigger(self, trigger: str, value: int, source: str, ttl_ms: int | None, controller: int) -> None: ...
    def reset(self, controller: int) -> None: ...

class VirtualGamepadActionAdapter:
    def execute(self, command: ActionCommand) -> ActionResult:
        ...
```

Map `left` and `right` stick names to the client axes `left_x/left_y` and
`right_x/right_y`. Forward a button's `pressed` flag as `press` or `release`.
Forward `lt`/`rt` to the client trigger method. `GAMEPAD_RESET` must call
`reset(controller)` without retaining input. Return metadata with controller,
source, TTL, and exact submitted values. Do not connect, start, pause, or
elevate the host from this adapter.

**Verify green**

```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_gamepad_action_adapter
# Expected: button, both stick axes, trigger, controller route, TTL, reset,
# and foreign-target rejection tests pass.
```

**Commit**

```text
feat: add reusable virtual gamepad action adapter
```

## Task 4: Integrate contracts without breaking mouse proof

**Files**

- Update `core/actions/models.py`
- Update `core/actions/mouse.py`
- Update `core/actions/__init__.py`
- Update `tests/test_mouse_action_adapter.py`
- Add `tests/test_actions_public_api.py`

**Test first**

```python
def test_mouse_adapter_accepts_a_generic_pointer_command(self):
    adapter = MouseActionAdapter(device=FakeMouseDevice(), clock_ms=lambda: 1, sleep=lambda _: None)
    command = ActionCommand(ActionKind.MOVE, PointerTarget(mapped_point))

    result = adapter.execute(command)

    self.assertEqual((480, 271), result.point)

def test_legacy_action_request_remains_compatible(self):
    result = adapter.execute(ActionRequest(ActionKind.MOVE, mapped_point))
    self.assertTrue(result.executed)
```

**Verify red**

```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_mouse_action_adapter tests.test_actions_public_api
# Expected: generic PointerTarget command is unsupported before integration.
```

**Implementation contract**

```python
def as_action_command(request: ActionRequest | ActionCommand) -> ActionCommand:
    if isinstance(request, ActionCommand):
        return request
    if isinstance(request, ActionRequest):
        return ActionCommand(request.kind, PointerTarget(request.point), interval_ms=request.interval_ms)
    raise TypeError(...)
```

Keep `ActionRequest` in `models.py` with its original public fields and
validation. Convert it at the mouse boundary. Export all new contracts and
both adapters from `core.actions`. The OCR proof must remain unchanged.

**Verify green**

```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_mouse_action_adapter tests.test_desktop_ocr_action_proof tests.test_actions_public_api
# Expected: legacy OCR proof and both legacy/generic mouse entry points pass.
```

**Commit**

```text
feat: expose composable keyboard and gamepad actions
```

## Task 5: Full regression and documentation handoff

**Files**

- Update `CODEBASE.md`
- Update `ITERATION_LOG.md` only if it has no unrelated user changes

**Verification**

```powershell
Set-Location D:\ACloud\auto_modules
D:\ACloud\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
# Expected: full test suite passes.

$env:PYTHONPATH = 'D:\ACloud\auto_modules;D:\ACloud\auto_modules\virtual_gamepad\client\python'
D:\ACloud\.venv\Scripts\python.exe -c "from core.actions import VirtualGamepadActionAdapter, KeyboardActionAdapter; print('action exports ready')"
# Expected: action exports ready
```

Only document the completed action-library contracts and explicit limitation:
the adapters send primitive commands, while navigation-to-stick steering and
workbench graph composition remain separate future modules.

**Commit**

```text
docs: record composable keyboard and gamepad action contracts
```
