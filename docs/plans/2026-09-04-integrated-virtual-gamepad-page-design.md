# Integrated Virtual Gamepad Page Design

## Goal

Make Virtual Gamepad a third first-class page in the `auto_modules` desktop
workbench while retaining the C# virtual-controller Host as an independent,
privileged process.

## User-visible outcome

The main workbench opens with its existing map and navigation pages unchanged
and adds a `虚拟手柄` page.  The page displays the existing controller diagram,
Controller 1/2 selector, keyboard and mouse binding controls, live input
state, and F7/F8/F9 safety hints in the workbench's existing dark visual style.
No separate `Virtual Gamepad` window is opened by normal workbench startup.

## Boundaries

### Remain independent

- `virtual_gamepad/host`: driver, XInput devices, low-level physical-input
  hooks, F7/F8/F9, safety state, and named-pipe server.
- `core.actions.VirtualGamepadActionAdapter`: programmatic button, stick,
  trigger, reset, route, source, and TTL commands.
- Game-specific navigation, steering, OCR, route planning, and automation
  policy.  They remain outside this UI integration.

### Move into the total UI

- The PySide controller editor/presenter currently under
  `virtual_gamepad/ui/virtual_gamepad_ui` becomes reusable as an embeddable
  `QWidget`; its standalone `QMainWindow` launcher remains only as an
  optional isolated diagnostic entry point.
- A total-workbench `GamepadHostManager` owns host startup, bounded readiness
  checks, a client connection, and safe shutdown for the process it started.

## Lifecycle and safety

```text
main.py (already elevated)
  -> MainWindow
  -> GamepadHostManager.start()
  -> independent C# Host process
  -> named-pipe ready
  -> embedded Virtual Gamepad page connects

MainWindow close
  -> page stops polling / closes client
  -> reset + pause Controller 1 and Controller 2
  -> close Host only if this workbench started it
```

The Host starts with both controllers paused.  Merely opening the total UI
must never intercept a mapped key or mouse button.  Mapping interception is
still activated only by Controller 1 F7 / Controller 2 F8 or the equivalent
page control.  Any page, client, or host startup failure is shown on the
Virtual Gamepad page; map and navigation pages continue to work.

The total UI has already elevated through `main.py`, so starting the Host from
that process does not request a second UAC prompt.  A separately launched
Host is not killed by the workbench on exit.

## UI design

The page is intentionally a visual adaptation, not a new product surface:

- add a third checked mode button: `虚拟手柄`;
- status header uses the workbench's surface cards and primary/success/warning
  tokens;
- Controller 1 / Controller 2 remain a compact selector; the selected
  controller's bindings and state are displayed;
- the controller diagram uses the existing physical layout but dark canvas,
  workbench border, muted labels, primary active input, and success running
  indication;
- existing keyboard dropdown and mouse dropdown binding flows remain intact;
- show F7, F8, F9 and clear `暂停时不会拦截键鼠` copy;
- retain Start/Pause and reset controls; do not add a node editor, macros, or
  motion-control settings in this page.

## Host communication

Both page and code actions talk to the same named-pipe Host.  The Host must
allow simultaneous same-user clients because the page maintains a status
connection while an automation module sends action commands.  The Python
client uses native Windows named-pipe handles rather than regular file I/O.

Programmatic Xbox input is supported after the Host is ready:

```python
route = VirtualControllerRoute(controller=1, source="auto_mode.workflow", ttl_ms=250)
adapter.execute(ActionCommand(ActionKind.GAMEPAD_STICK, GamepadStickTarget(route, "left", 0, 24000)))
```

Higher-level callers must refresh held values before TTL expiry and reset on
completion or cancellation.  The page is a monitor/configurator; it does not
own automation decisions.

## Verification

- Unit tests cover Windows client line transport injection and Host concurrent
  clients.
- Offscreen Qt tests prove the total UI exposes the third page and that it
  does not start mapping by construction.
- Host-manager tests prove bounded startup failure, ownership-aware shutdown,
  and reset/pause of both controllers.
- Manual Windows acceptance proves a single total UI starts Host, displays the
  page, accepts Controller 1/2 binding edits, and permits a simultaneous
  `VirtualGamepadActionAdapter` command.  Closing the total UI must leave both
  controllers paused and physical inputs unlocked.
