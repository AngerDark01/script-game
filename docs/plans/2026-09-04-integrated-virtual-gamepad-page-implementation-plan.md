# Integrated Virtual Gamepad Page Implementation Plan

## Goal

Embed the existing Virtual Gamepad controls as a visual-style-consistent third
page of the total `auto_modules` UI, while starting and safely stopping the
independent Host with the total application.

## Architecture Overview

`main.py` remains the only UAC boundary for the combined workbench.  A
`GamepadHostManager` starts or attaches to the C# Host without launching the
old standalone UI.  An embeddable `GamepadPage` reuses the existing controller
diagram, profiles, bindings, and status refresh.  `MainWindow` owns the
manager and page, but uses no direct driver or hook API.  Existing
`core.actions` programmatic Xbox adapters continue to use the shared Host pipe.

## Tech Stack

- Python 3.12, PySide6, `unittest`
- C# / .NET 8 named-pipe Host
- Win32 named-pipe client through `ctypes`
- Existing ViGEm XInput Host and JSON-lines protocol

### Task 1: Commit and lock the shared-pipe transport boundary

Files:

- `virtual_gamepad/client/python/virtual_gamepad_client.py`
- `virtual_gamepad/client/python/tests/test_client_protocol.py`
- `virtual_gamepad/host/src/VirtualGamepadHost/Protocol/NamedPipeServer.cs`
- `virtual_gamepad/host/tests/VirtualGamepadHost.Tests/ConcurrentPipeTests.cs`
- `virtual_gamepad/scripts/start_virtual_gamepad.py`

The Python client accepts an injectable `pipe_opener` for unit tests; the
production opener uses `_WindowsNamedPipe` with `WaitNamedPipeW`,
`CreateFileW`, `ReadFile`, and `WriteFile`.  The C# server uses
`MaxAllowedServerInstances` and moves an accepted client to
`ServeClientAsync`, immediately returning to accept another client.

Regression test first:

```python
def test_connect_uses_a_pipe_opener_for_a_real_line_transport():
    pipe = _LinePipe()
    client = VirtualGamepadClient(
        pipe_path=r"\\.\pipe\test",
        pipe_opener=lambda path: pipe,
    )
    client.connect()
    assert client.status() == {"connected": True}
```

```csharp
[Fact]
public async Task UiAndAutomationClientsCanIssueRequestsWhileBothRemainConnected()
{
    await using var ui = await ConnectAsync(pipeName);
    await AssertHelloAsync(ui);
    await using var automation = await ConnectAsync(pipeName);
    await AssertHelloAsync(automation);
}
```

Verify:

```powershell
D:\ACloud\dotnet-sdk2\dotnet.exe test virtual_gamepad\host\tests\VirtualGamepadHost.Tests\VirtualGamepadHost.Tests.csproj --no-restore
# Expected: 32 tests passed, including ConcurrentPipeTests.

$env:PYTHONPATH = 'D:\ACloud\auto_modules\virtual_gamepad\client\python;D:\ACloud\auto_modules\virtual_gamepad\client\python\tests'
D:\ACloud\.venv\Scripts\python.exe -c "import test_client_protocol as t; t.test_connect_uses_a_pipe_opener_for_a_real_line_transport()"
# Expected: exit 0.
```

Commit: `fix: support concurrent native-pipe gamepad clients`

### Task 2: Extract an embeddable dark-theme GamepadPage

Files:

- Add `virtual_gamepad/ui/virtual_gamepad_ui/gamepad_page.py`
- Update `virtual_gamepad/ui/virtual_gamepad_ui/main_window.py`
- Update `virtual_gamepad/ui/virtual_gamepad_ui/controller_widget.py`
- Add `virtual_gamepad/ui/tests/test_gamepad_page.py`

Move the existing page-building, profile, binding, selected-controller, timer,
and `shutdown()` responsibilities from `MainWindow` into:

```python
class GamepadPage(QWidget):
    def __init__(self, client: VirtualGamepadClient, *, profile_root: Path, parent=None) -> None: ...
    def shutdown(self) -> None:
        self.client.pause(1)
        self.client.pause(2)
        self.client.close()
```

`MainWindow` becomes a small standalone wrapper that creates a `GamepadPage`
as its central widget.  Preserve the existing keyboard and mouse dropdown
flows and profile format.  Replace only the controller-widget hard-coded light
palette with the total UI tokens: `#0B1220`, `#111C2B`, `#26364A`, `#91A4B8`,
`#38BDF8`, and `#22C55E`.

Test first:

```python
def test_page_selects_controller_two_and_keeps_mouse_bindings_dropdown_based(qtbot):
    page = GamepadPage(FakeClient(), profile_root=tmp_path)
    qtbot.addWidget(page)
    page._select_controller(2)
    assert page.selected_controller == 2
    assert page.mouse_combo.count() > 0
```

Verify:

```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest virtual_gamepad.ui.tests.test_gamepad_page virtual_gamepad.ui.tests.test_main_window_bindings
# Expected: all page/binding tests pass offscreen.
```

Commit: `refactor: make virtual gamepad controls embeddable`

### Task 3: Add ownership-aware Host lifecycle management

Files:

- Add `gui/gamepad/__init__.py`
- Add `gui/gamepad/host_manager.py`
- Add `tests/test_gamepad_host_manager.py`

Introduce a UI-independent service:

```python
class GamepadHostManager:
    def start(self, timeout: float = 5.0) -> HostStartResult: ...
    def create_client(self) -> VirtualGamepadClient: ...
    def shutdown(self) -> None: ...
```

`start()` first attempts a short shared-pipe connection.  If unavailable, it
starts `VirtualGamepadHost.dll` using the workspace .NET runtime and waits a
bounded period for the pipe.  It records `owns_host=True` only for the process
it starts.  `shutdown()` sends reset and pause for controllers 1/2 via a fresh
client, closes all clients it owns, and terminates only its owned process.
It must never invoke a second UAC prompt; `main.py` already guarantees the
total UI runs elevated.

Test first with fake client/process/clock dependencies:

```python
def test_shutdown_resets_and_pauses_both_controllers_then_stops_only_owned_host():
    manager = GamepadHostManager(client_factory=lambda: fake_client, process_factory=lambda *_: fake_process)
    manager.start()
    manager.shutdown()
    assert fake_client.calls == [("reset", 1), ("pause", 1), ("reset", 2), ("pause", 2)]
    fake_process.terminate.assert_called_once()
```

Verify:

```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_gamepad_host_manager
# Expected: startup, failed readiness, attached-host, and safe shutdown tests pass.
```

Commit: `feat: manage virtual gamepad host from workbench`

### Task 4: Register the total UI page without altering existing modes

Files:

- Update `gui/main_window.py`
- Update `gui/theme.py`
- Add `tests/test_gamepad_page_in_main_window.py`

Inject `GamepadHostManager` into `MainWindow` for tests.  During window
construction, call manager startup once and construct `GamepadPage` with an
attached client or a disconnected error-state client.  Add only one new mode
button and one `QStackedWidget` entry:

```python
self.mode_btn_gamepad = QPushButton("虚拟手柄")
self.mode_btn_gamepad.setProperty("role", "mode")
self.mode_buttons = [self.mode_btn_mapping, self.mode_btn_nav, self.mode_btn_gamepad]
self.gamepad_page = GamepadPage(client, profile_root=GAMEPAD_CONFIG_ROOT, parent=self)
self.stacked_widget.addWidget(self.gamepad_page)
```

On `closeEvent`, call `gamepad_page.shutdown()` followed by
`gamepad_host_manager.shutdown()` after the existing mapping/navigation
shutdowns.  Avoid changing the layout or controls of map and navigation pages.

Test first:

```python
def test_main_window_exposes_gamepad_as_third_page_and_shuts_it_down():
    manager = FakeHostManager()
    window = MainWindow(gamepad_host_manager=manager)
    window.switch_mode(2)
    assert window.stacked_widget.currentWidget() is window.gamepad_page
    window.close()
    assert manager.shutdown_called
```

Verify:

```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_gamepad_page_in_main_window tests.test_navigation_ui_layout tests.test_navigation_compact_actions
# Expected: third page passes and old modes retain their layout behavior.
```

Commit: `feat: add virtual gamepad page to workbench`

### Task 5: Run the live two-client acceptance path and document it

Files:

- Update `docs/action-library.md`
- Update `virtual_gamepad/docs/acceptance.md`
- Update `README.md`

Start the elevated total UI.  Confirm only one visible UI appears, then use
the embedded page to verify the Host/driver state.  With the embedded page
still connected, launch `utils/live_action_library_probe.py` at the same
integrity level.  It must record a matching state for A, RT and LS, then reset
and pause Controller 1.  Check that both controllers are paused on total UI
close and a mapped key is again ordinary keyboard input.

Verify:

```powershell
D:\ACloud\.venv\Scripts\python.exe main.py
# Expected: one total UI window opens with the 虚拟手柄 page.

D:\ACloud\.venv\Scripts\python.exe utils\live_action_library_probe.py --controller 1
Get-Content logs\live_action_library_probe.json
# Expected: "success": true and cleanup reports reset/paused true.
```

Commit: `docs: describe integrated virtual gamepad workbench page`
