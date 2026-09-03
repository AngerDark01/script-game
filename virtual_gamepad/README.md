# Virtual Gamepad Module

This directory contains the independent Windows virtual controller feature for `auto_modules`.

## Components

- `host`: C#/.NET 8 background process that owns ViGEmBus, Raw Input, mapping, safety, and the Named Pipe.
- `ui`: PySide6 live monitor and binding editor.
- `client/python`: standard-library client for automation modules.
- `protocol`: versioned JSON-lines messages.

## Development setup

1. Install the .NET 8 SDK.
2. Install the signed ViGEmBus driver. Check it with `scripts/check_driver.ps1`.
3. Build and test the host:

   ```powershell
   dotnet test host/VirtualGamepadHost.sln
   ```

4. Start the host:

   ```powershell
   dotnet run --project host/src/VirtualGamepadHost
   ```

5. Start the UI in another terminal:

   ```powershell
   $env:PYTHONPATH = (Resolve-Path client/python)
   $env:PYTHONPATH = "$env:PYTHONPATH;$(Resolve-Path ui)"
   python -m virtual_gamepad_ui.main
   ```

Use `python -m virtual_gamepad_ui.main --demo` to inspect the UI without a host or driver.

## Python control example

```python
from virtual_gamepad_client import VirtualGamepadClient

with VirtualGamepadClient() as pad:
    pad.start()
    pad.press("A", ttl_ms=500)
    pad.set_axis("left_y", 32767, ttl_ms=500)
    pad.emergency_reset()
```

The host uses a user-local pipe named `AutoModules.VirtualGamepad.v1`. It sends a complete neutral report on pause, reset, client timeout, and shutdown.

## Current limitations

The first release exposes one Xbox 360 XInput device and observes physical keyboard/mouse input without suppressing it. DirectInput, DualShock, multiple devices, passthrough, macros, and anti-cheat workarounds are intentionally not included.
