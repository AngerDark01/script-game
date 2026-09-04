# Dual-controller virtual gamepad implementation plan

## Goal

Upgrade the independent Windows virtual-gamepad module from one virtual Xbox
360 device to two independently configured Xbox 360 devices that may operate
concurrently from the same physical keyboard and mouse.

## Architecture overview

- One elevated C# host creates and owns two ViGEm Xbox 360 targets.
- Each controller slot owns its own `StateStore`, `SafetyController`, and
  `MappingEngine`.
- One low-level keyboard/mouse hook fans each input event out to every running
  slot. A source is swallowed only if at least one running slot binds it.
- F7 toggles slot 1; F8 toggles slot 2; F9 emergency-resets both slots.
- The pipe protocol accepts an optional `controller` number. Omission means
  controller 1 for existing clients.
- The UI retains one high-quality controller editor but adds a controller-1 /
  controller-2 selector and always-visible state summary for both devices.

## Tech stack

- C# / .NET 8 Windows Forms host
- `Nefarius.ViGEm.Client` 1.21.256
- Python 3.12, PySide6 UI, standard-library JSON-lines pipe client
- xUnit and pytest

## Task 1: Add a two-target ViGEm backend

Files:

- Modify `D:\ACloud\auto_modules\virtual_gamepad\host\src\VirtualGamepadHost\Driver\IXInputBackend.cs`
- Modify `D:\ACloud\auto_modules\virtual_gamepad\host\src\VirtualGamepadHost\Driver\ViGEmXInputBackend.cs`
- Modify `D:\ACloud\auto_modules\virtual_gamepad\host\src\VirtualGamepadHost\Driver\NullXInputBackend.cs`
- Modify `D:\ACloud\auto_modules\virtual_gamepad\host\tests\VirtualGamepadHost.Tests\FakeXInputBackend.cs`
- Add `D:\ACloud\auto_modules\virtual_gamepad\host\tests\VirtualGamepadHost.Tests\MultiBackendTests.cs`

1. Write the failing test:

```csharp
[Fact]
public void BackendSubmitsIndependentReportsForEachController()
{
    var backend = new FakeXInputBackend(controllerCount: 2);
    backend.Start();

    backend.Submit(1, GamepadState.Neutral.WithButton(GamepadButton.A, true));
    backend.Submit(2, GamepadState.Neutral.WithButton(GamepadButton.B, true));

    Assert.True(backend.LastState(1).IsPressed(GamepadButton.A));
    Assert.False(backend.LastState(1).IsPressed(GamepadButton.B));
    Assert.True(backend.LastState(2).IsPressed(GamepadButton.B));
    Assert.False(backend.LastState(2).IsPressed(GamepadButton.A));
}
```

2. Change the backend contract to use a one-based controller number:

```csharp
public interface IXInputBackend : IDisposable
{
    bool IsConnected { get; }
    int ControllerCount { get; }
    void Start();
    void Submit(int controller, GamepadState state);
    void Stop();
}
```

3. Store two `IXbox360Controller` targets in `ViGEmXInputBackend`, create both
from one `ViGEmClient`, and validate controller values are in `1..2` before a
report is submitted. `Stop()` must submit `GamepadState.Neutral` to both before
disconnecting either target.

Verify:

```powershell
& 'D:\ACloud\dotnet-sdk2\dotnet.exe' test 'D:\ACloud\auto_modules\virtual_gamepad\host\tests\VirtualGamepadHost.Tests\VirtualGamepadHost.Tests.csproj' --configuration Release --no-restore --filter MultiBackendTests
# Expected: 1 passed
```

Commit: `feat: add two-target ViGEm backend`

## Task 2: Create independent controller slots and reporting

Files:

- Add `D:\ACloud\auto_modules\virtual_gamepad\host\src\VirtualGamepadHost\Runtime\ControllerSlot.cs`
- Add `D:\ACloud\auto_modules\virtual_gamepad\host\src\VirtualGamepadHost\Runtime\ControllerRegistry.cs`
- Modify `D:\ACloud\auto_modules\virtual_gamepad\host\src\VirtualGamepadHost\Runtime\ReportLoop.cs`
- Modify `D:\ACloud\auto_modules\virtual_gamepad\host\src\VirtualGamepadHost\Runtime\HostComposition.cs`
- Add `D:\ACloud\auto_modules\virtual_gamepad\host\tests\VirtualGamepadHost.Tests\ControllerRegistryTests.cs`

1. Write failing isolation tests:

```csharp
[Fact]
public void SlotStatesDoNotBleedAcrossControllers()
{
    var registry = ControllerRegistry.CreateDefault(new FakeXInputBackend(controllerCount: 2));
    registry[1].Store.SetButton("test", GamepadButton.A, true);

    Assert.True(registry[1].Store.Snapshot().IsPressed(GamepadButton.A));
    Assert.False(registry[2].Store.Snapshot().IsPressed(GamepadButton.A));
}
```

2. Implement the slot record and registry:

```csharp
public sealed record ControllerSlot(
    int Number,
    StateStore Store,
    SafetyController Safety,
    MappingEngine Mapping);
```

`ControllerRegistry` creates slots 1 and 2, validates numbers, reports each
slot state to the matching backend target every 8 ms, and has `EmergencyResetAll()`.

3. Replace the single `StateStore`, `SafetyController`, `MappingEngine`, and
single-state `ReportLoop` composition with the registry. Host shutdown calls
`EmergencyResetAll()` before stopping the backend.

Verify:

```powershell
& 'D:\ACloud\dotnet-sdk2\dotnet.exe' test 'D:\ACloud\auto_modules\virtual_gamepad\host\tests\VirtualGamepadHost.Tests\VirtualGamepadHost.Tests.csproj' --configuration Release --no-restore --filter ControllerRegistryTests
# Expected: all isolation and dual-neutralisation tests pass
```

Commit: `feat: add independent controller slots`

## Task 3: Fan out physical input and add per-slot F7/F8 control

Files:

- Modify `D:\ACloud\auto_modules\virtual_gamepad\host\src\VirtualGamepadHost\Input\RawInputCapture.cs`
- Modify `D:\ACloud\auto_modules\virtual_gamepad\host\src\VirtualGamepadHost\Runtime\HostComposition.cs`
- Add `D:\ACloud\auto_modules\virtual_gamepad\host\tests\VirtualGamepadHost.Tests\DualMappingTests.cs`

1. First add tests for independent and shared sources:

```csharp
[Fact]
public void SharedSourceIsAppliedToBothRunningSlots()
{
    var first = NewSlot(1, new Binding("keyboard:J", "button:A"));
    var second = NewSlot(2, new Binding("keyboard:J", "button:B"));
    first.Safety.Start();
    second.Safety.Start();

    ApplyToRunningSlots(new PhysicalInput("keyboard:J", PhysicalInputType.KeyDown), first, second);

    Assert.True(first.Store.Snapshot().IsPressed(GamepadButton.A));
    Assert.True(second.Store.Snapshot().IsPressed(GamepadButton.B));
}
```

2. Replace the one-input action passed to `RawInputCapture` with a dispatcher:

```csharp
void ApplyPhysicalInput(PhysicalInput input)
{
    foreach (var slot in registry.Slots.Where(slot => slot.Safety.RunState == RunState.Running))
    {
        slot.Mapping.Apply(input);
    }
}

bool ShouldSuppress(PhysicalInput input) => registry.Slots.Any(slot =>
    slot.Safety.RunState == RunState.Running && slot.Mapping.ShouldSuppress(input));
```

3. Register F7 for slot 1 and F8 for slot 2. Keep F9 global. The hotkey enum and
callback should explicitly name `ToggleController1`, `ToggleController2`, and
`EmergencyResetAll`.

4. Add regression coverage that F7 changes only slot 1, F8 only slot 2, and F9
returns both stores to neutral and paused.

Verify:

```powershell
& 'D:\ACloud\dotnet-sdk2\dotnet.exe' test 'D:\ACloud\auto_modules\virtual_gamepad\host\tests\VirtualGamepadHost.Tests\VirtualGamepadHost.Tests.csproj' --configuration Release --no-restore --filter DualMappingTests
# Expected: shared key fan-out, independent pause, and global emergency reset pass
```

Commit: `feat: fan out mapped input across controller slots`

## Task 4: Extend pipe routing and preserve controller-1 compatibility

Files:

- Modify `D:\ACloud\auto_modules\virtual_gamepad\host\src\VirtualGamepadHost\Protocol\CommandRouter.cs`
- Modify `D:\ACloud\auto_modules\virtual_gamepad\host\src\VirtualGamepadHost\Runtime\HostStatus.cs`
- Modify `D:\ACloud\auto_modules\virtual_gamepad\client\python\virtual_gamepad_client.py`
- Modify `D:\ACloud\auto_modules\virtual_gamepad\client\python\tests\test_client_protocol.py`
- Modify `D:\ACloud\auto_modules\virtual_gamepad\host\tests\VirtualGamepadHost.Tests\ProtocolTests.cs`

1. Add a failing host test proving controller 2 receives a command without
changing controller 1:

```csharp
var command = ProtocolSerializer.Parse("""
{"id":"2","type":"button","payload":{"controller":2,"source":"test","button":"A","action":"press"}}
""");
Assert.Contains("\"ok\":true", router.Handle(command));
Assert.False(registry[1].Store.Snapshot().IsPressed(GamepadButton.A));
Assert.True(registry[2].Store.Snapshot().IsPressed(GamepadButton.A));
```

2. Add a `controller` property to every state/config command payload. Centralise
validation in:

```csharp
private ControllerSlot Slot(int? controller) => _registry.Get(controller ?? 1);
```

3. Update Python methods to take keyword-only controller `1` by default:

```python
def state(self, controller: int = 1) -> dict[str, Any]:
    return self.request("get_state", {"controller": controller})

def start(self, controller: int = 1) -> None:
    self.request("start", {"controller": controller})
```

4. Define `emergency_reset()` with no controller as an intentional all-slot
operation; do not add a slot-specific emergency reset to avoid accidental
partial safety cleanup.

Verify:

```powershell
& 'D:\ACloud\dotnet-sdk2\dotnet.exe' test 'D:\ACloud\auto_modules\virtual_gamepad\host\tests\VirtualGamepadHost.Tests\VirtualGamepadHost.Tests.csproj' --configuration Release --no-restore --filter ProtocolTests
python -m pytest D:\ACloud\auto_modules\virtual_gamepad\client\python\tests -q
# Expected: existing controller-1 calls remain valid and controller-2 calls isolate state
```

Commit: `feat: route pipe commands to independent controllers`

## Task 5: Store and load separate controller profiles

Files:

- Add `D:\ACloud\auto_modules\virtual_gamepad\configs\controller-1.json`
- Add `D:\ACloud\auto_modules\virtual_gamepad\configs\controller-2.json`
- Modify `D:\ACloud\auto_modules\virtual_gamepad\configs\default.json`
- Modify `D:\ACloud\auto_modules\virtual_gamepad\ui\virtual_gamepad_ui\profile_store.py`
- Modify `D:\ACloud\auto_modules\virtual_gamepad\ui\tests\test_profile_store.py`

1. Write a failing pytest that loads the two dedicated profile paths and proves
edits saved to one do not change the other.

2. Keep the existing mapping JSON shape per file, with slot-specific start
labels:

```json
{
  "bindings": { "A": ["keyboard:Space"] },
  "startPause": "F7",
  "emergencyReset": "F9"
}
```

Controller 2 uses `"startPause": "F8"`. `default.json` remains a
controller-1-compatible fallback for existing users.

3. Add `load_profiles(controller_one_path, controller_two_path)` and
`save_profile(path, profile)` coverage without changing legacy load behaviour.

Verify:

```powershell
$env:PYTHONPATH = 'D:\ACloud\auto_modules\virtual_gamepad\ui;D:\ACloud\auto_modules\virtual_gamepad\client\python'
python -m pytest D:\ACloud\auto_modules\virtual_gamepad\ui\tests\test_profile_store.py -q
# Expected: controller-1 and controller-2 profiles persist independently
```

Commit: `feat: add independent controller profiles`

## Task 6: Add dual-slot UI state and selected-controller routing

Files:

- Modify `D:\ACloud\auto_modules\virtual_gamepad\ui\virtual_gamepad_ui\models.py`
- Modify `D:\ACloud\auto_modules\virtual_gamepad\ui\virtual_gamepad_ui\main_window.py`
- Modify `D:\ACloud\auto_modules\virtual_gamepad\ui\virtual_gamepad_ui\main.py`
- Modify `D:\ACloud\auto_modules\virtual_gamepad\ui\tests\test_models.py`
- Modify `D:\ACloud\auto_modules\virtual_gamepad\ui\tests\test_main_window_bindings.py`

1. Add a failing model test:

```python
def test_dual_status_reads_both_controller_slots():
    status = DualUiStatus.from_payload({
        "controllers": [{"controller": 1, "runState": "running"}, {"controller": 2, "runState": "paused"}]
    })
    assert status.for_controller(1).run_state == "running"
    assert status.for_controller(2).run_state == "paused"
```

2. Add a compact two-slot status strip and selector buttons:

```python
self.controller_one_selector = QPushButton("Controller 1 · F7")
self.controller_two_selector = QPushButton("Controller 2 · F8")
self.controller_one_selector.clicked.connect(lambda: self._select_controller(1))
self.controller_two_selector.clicked.connect(lambda: self._select_controller(2))
```

3. Keep one editable controller diagram. Switching selected controller replaces
only the displayed profile/state. Route `_apply_profile`, `_start`, `_pause`,
and `refresh` to `self.selected_controller`.

4. Make UI close call `client.emergency_reset()` once, then close the pipe, so
both devices are neutralised.

Verify:

```powershell
$env:PYTHONPATH = 'D:\ACloud\auto_modules\virtual_gamepad\ui;D:\ACloud\auto_modules\virtual_gamepad\client\python'
python -m pytest D:\ACloud\auto_modules\virtual_gamepad\ui\tests -q
# Expected: profile edits are tagged with controller 1 or 2; close sends global emergency reset
```

Commit: `feat: add two-controller mapping UI`

## Task 7: Update launcher, diagnostics, and user-facing verification

Files:

- Modify `D:\ACloud\auto_modules\virtual_gamepad\scripts\start_virtual_gamepad.py`
- Modify `D:\ACloud\auto_modules\virtual_gamepad\scripts\live_gamepad_probe.py`
- Modify `D:\ACloud\auto_modules\virtual_gamepad\docs\acceptance.md`
- Modify `D:\ACloud\auto_modules\virtual_gamepad\README.md`
- Modify `D:\ACloud\auto_modules\virtual_gamepad\scripts\tests\test_start_virtual_gamepad.py`
- Modify `D:\ACloud\auto_modules\virtual_gamepad\scripts\tests\test_live_gamepad_probe.py`

1. Add tests for controller-number propagation in the launcher/probe.
2. Extend the live probe with `--controller 1|2`; use controller-specific
`get_config`, `set_config`, `start`, `state`, then execute global emergency
reset in `finally`.
3. Update the launcher success message and UI hints to describe F7, F8, and F9.
4. Extend acceptance documentation with `joy.cpl` verification that two
Xbox 360 controllers are visible and shared keys affect both only when bound in
both profiles.

Verify:

```powershell
& 'D:\ACloud\dotnet-sdk2\dotnet.exe' test 'D:\ACloud\auto_modules\virtual_gamepad\host\tests\VirtualGamepadHost.Tests\VirtualGamepadHost.Tests.csproj' --configuration Release --no-restore
$env:PYTHONPATH = 'D:\ACloud\auto_modules;D:\ACloud\auto_modules\virtual_gamepad\ui;D:\ACloud\auto_modules\virtual_gamepad\client\python'
python -m pytest D:\ACloud\auto_modules\virtual_gamepad\ui\tests D:\ACloud\auto_modules\virtual_gamepad\client\python\tests D:\ACloud\auto_modules\virtual_gamepad\scripts\tests -q
# Expected: all C# and Python tests pass
```

Commit: `docs: document dual-controller operation and verification`

## Task 8: Elevated live validation and safety handoff

Files:

- No persistent code change unless a failing acceptance check reveals one.

1. Start the existing one-click elevated launcher.
2. Confirm `joy.cpl` exposes two Xbox 360 controllers.
3. Verify controller 1 and controller 2 state independently from the elevated
UI using different bindings.
4. Bind one harmless key to one button on both slots; start both slots and
confirm both visual controller diagrams activate while the physical source is
suppressed exactly once.
5. Test F7, F8, then F9; leave both slots paused before handing back control.

Verify:

```text
Controller 1: paused, neutral
Controller 2: paused, neutral
No configured physical input remains locked
```

Commit: `test: validate dual-controller behaviour in elevated environment`
