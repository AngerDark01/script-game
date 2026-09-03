# Acceptance Checklist

## Software-only checks

- `dotnet test host/tests/VirtualGamepadHost.Tests` passes.
- `python -m pytest ui/tests` passes.
- `python -m pytest client/python/tests` passes.
- `python -m virtual_gamepad_ui.main --demo` opens the controller monitor.
- The host prints a pipe name and remains usable when ViGEmBus is missing.

## Windows device check

1. Install the signed ViGEmBus driver once with administrator approval.
2. Run `scripts/check_driver.ps1` and confirm it reports the device.
3. Start the host, then inspect `joy.cpl`.
4. Confirm one Xbox 360 Controller is present.
5. Use the Python client or UI to press every button, move both sticks, and change both triggers.
6. Confirm pause and F9 emergency reset return every control to neutral.
7. Start the target game and verify it responds through XInput.

The host does not install drivers silently and does not bypass anti-cheat or suppress physical keyboard/mouse input.
