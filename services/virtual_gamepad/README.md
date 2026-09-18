# Virtual Gamepad Module

This directory contains the independent Windows virtual controller feature for `auto_modules`.

## Components

- `host`: C#/.NET 8 background process that owns two independent ViGEmBus Xbox 360 targets, low-level keyboard/mouse hooks, mapping, safety, and the Named Pipe.
- `../../src/auto_modules/ui/virtual_gamepad`: PySide6 live monitor and binding editor.
- `../../src/auto_modules/adapters/virtual_gamepad`: standard-library client and action adapter for automation modules.
- `protocol`: versioned JSON-lines messages.

## Daily startup

For normal use, double-click [启动 Virtual Gamepad.exe](./启动%20Virtual%20Gamepad.exe) in this service directory. It requests Administrator permission once, reuses an already-running host when possible, then opens the mapping UI. It starts both controller slots; use F7 for controller 1, F8 for controller 2, and F9 to emergency-reset both.

`VirtualGamepadHost.exe` under `host` is only the background host and is not the normal UI entry point.

## Development setup

1. Install the .NET 8 SDK.
2. Install the signed ViGEmBus driver. From the repository root, check it with `tools/virtual_gamepad/check_driver.ps1`.
3. Build and test the host:

   ```powershell
   dotnet test services/virtual_gamepad/host/VirtualGamepadHost.sln
   ```

4. Start the host:

   ```powershell
   dotnet run --project services/virtual_gamepad/host/src/VirtualGamepadHost
   ```

   The host automatically requests Administrator permission. This is required
   when mapping input for a game that itself runs as Administrator. Starting
   the compiled host directly displays the same Windows UAC confirmation.

5. Start the UI in another terminal:

   ```powershell
   $env:PYTHONPATH = (Resolve-Path src)
   python -m auto_modules.ui.virtual_gamepad.main
   ```

   The non-demo UI automatically requests Administrator permission as well,
   so it can connect to the elevated host's user-local pipe. Demo mode stays
   unelevated because it does not access the host.

   To start both the elevated host and the visible UI with one UAC prompt,
   run the independent launcher:

   ```powershell
   D:\ACloud\.venv\Scripts\python.exe D:\ACloud\auto_modules\tools\virtual_gamepad\start_virtual_gamepad.py
   ```

   The launcher waits for the host pipe before opening the UI. The host itself
   is a background process, while `Virtual Gamepad` is the window you should
   use for bindings and Start/Pause controls.

Use `$env:PYTHONPATH = (Resolve-Path src); python -m auto_modules.ui.virtual_gamepad.main --demo` from the repository root to inspect the UI without a host or driver.

## LAN controller synchronization

The workbench's controller page now contains a **设备同步** tab (also available
in the standalone mapping UI). The host loads the independent sibling module
`../lan_input_sync`; the UI does not own network connections. No extra manual
background process is required. Network mode and input permissions start off
each time the host starts; saved device names, addresses and pairing trust are
retained without automatically resuming control.

On each receiving PC, select receive mode and its actual LAN IPv4 address,
apply settings, generate a temporary device code and allow the desired
controller slots. On the sending PC, select send mode, apply settings, discover
or enter the receiver address and its code. Compare the confirmation code on
both screens and confirm on **both** PCs. Select the paired receiver, choose
Controller 1 and/or 2 and start synchronization. Repeat for additional receivers.
Start the sender's local mappings with F7/F8 to produce input.

Only final Xbox reports are sent, including program-generated host actions;
raw keyboard/mouse events are not injected into another PC. A receiver-owned
slot does not intercept that PC's local input. Other locally owned slots still
follow their own mapping settings. F7/F8 toggle permission for the corresponding
remote slot; F9 stops all sessions and releases output. After loss or F9, enable
reception and explicitly start sending again. Merely restoring the network does
not replay queued actions.

Both PCs need this updated software and their own installed ViGEmBus driver.
Use a trusted private LAN; allow the host on Windows Firewall's private profile
if prompted. The default is TCP/UDP 45873, limited by configuration to a concrete
private IPv4 address. Do not expose or forward this port to the Internet. Do not
copy per-user device identity or trust files to the other PC.

See [LAN module guide](../lan_input_sync/README.md) for protocol boundaries,
configuration and verification details. A full source checkout for building
this host must include the sibling `lan_input_sync` directory. Compiled host
deployment includes `LanInputSync.dll` and its dependencies alongside the host.

## Python control example

```python
from auto_modules.adapters.virtual_gamepad import VirtualGamepadClient

with VirtualGamepadClient() as pad:
    pad.start()
    pad.press("A", ttl_ms=500)
    pad.set_axis("left_y", 32767, ttl_ms=500)
    pad.emergency_reset()
```

The host uses a user-local pipe named `AutoModules.VirtualGamepad.v1`. It sends a complete neutral report on pause, reset, client timeout, and shutdown. The pipe deliberately accepts only the same Windows user at the same permission level; automation clients that control a real elevated game should likewise run as Administrator.

The shortcuts are `F7` for controller 1, `F8` for controller 2, and `F9` for an emergency reset of both. The UI has separate controller-1 and controller-2 profiles; a physical source is forwarded to every running slot that binds it. In the UI, choose a key from `Choose keyboard` and click `Set` (or `Add` for multi-key controls); mouse bindings use the `Mouse binding` dropdown and are never captured from clicks.

For mouse-to-right-stick camera control, `RS mouse sensitivity` is stored independently in each controller profile. The default is `4.00×`, four times the prior mapping speed; adjust it in the UI and use `Save profile` to persist it. `Keep native mouse movement while mirroring to RS` is enabled by default: mouse movement simultaneously reaches the game at its normal speed and drives RS. Disable it when a game requires pure controller camera input; in that mode mapped mouse movement is consumed and drives only RS. `LS Click (L3)` and `RS Click (R3)` are separate controls: select `LeftStickClick` or `RightStickClick` in the binding list (or click their L3/R3 boxes on the virtual controller), then choose a keyboard key and press `Set`. They are unbound by default.

## Current limitations

The first release exposes two Xbox 360 XInput devices. While mapping is running, configured keyboard and mouse-button sources are consumed once and forwarded to every running slot that binds them; unconfigured input still passes through. Mapped mouse movement is the deliberate exception: its new default is to pass through natively while also driving RS, and the UI toggle can restore pure-RS consumed movement. Press `F7`/`F8` to pause one slot and restore its inputs, or `F9` for a global emergency reset. DirectInput, DualShock, passthrough, macros, and anti-cheat workarounds are intentionally not included. Games running with elevated permissions require the host and any input-sending automation to run at the same permission level. The independent host, UI, and live probe request that permission automatically; dismissing the Windows UAC prompt leaves mapping paused and no physical input is suppressed.
