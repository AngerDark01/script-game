# Acceptance Checklist

## Software-only checks

- `D:\ACloud\dotnet-sdk2\dotnet.exe test services/virtual_gamepad/host/tests/VirtualGamepadHost.Tests/VirtualGamepadHost.Tests.csproj --no-restore` passes.
- `D:\ACloud\.venv\Scripts\python.exe -m pytest tests/virtual_gamepad_ui tests/virtual_gamepad_client -q` passes.
- `D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_gamepad_host_manager tests.test_gamepad_page_in_main_window` passes.
- `$env:PYTHONPATH = (Resolve-Path src); python -m auto_modules.ui.virtual_gamepad.main --demo` remains available as an isolated diagnostic UI.
- The Host creates its pipe and remains observable even if ViGEmBus is missing; it must start with both mappings paused.

## Windows device check

1. Start the total workbench with `D:\ACloud\.venv\Scripts\python.exe main.py` from `D:\ACloud\auto_modules`, then approve its single UAC request.
2. Confirm one `auto_modules` window opens and its top bar contains the `🎮 虚拟手柄` page. Normal use must not open a second `Virtual Gamepad` window.
3. Install the signed ViGEmBus driver once with administrator approval, inspect `joy.cpl`, and confirm two Xbox 360 Controllers are present.
4. In the embedded page, configure Controller 1 and Controller 2 independently. Keyboard mappings use the Choose keyboard dropdown with Set/Add; mouse mappings use the Mouse binding dropdown and are never captured from clicks.
5. Start Controller 1 with F7 and Controller 2 with F8. A shared key should affect both only when it is bound in both profiles; a key bound in one profile must not affect the other. Confirm the configured keyboard and mouse-button inputs activate their virtual controller mappings and are not delivered as their original events.
6. Confirm F7/F8 pause independently and F9 emergency-reset returns both controls to neutral. After pausing, each mapped physical key must once again be ordinary system input.
7. Bind `mouse:move_x` / `mouse:move_y` to `RightStick`, then tune RS mouse sensitivity independently for each controller. With Keep native mouse movement enabled, confirm the game still receives normal mouse movement while RS updates; disabling it consumes movement and drives only RS. Confirm LeftStickClick maps to L3 and RightStickClick maps to R3.
8. Start the target game and verify it responds through XInput while focused. With mapping enabled, confirm raw mapped keyboard/mouse input is not also delivered as normal keyboard/mouse input.
9. With the embedded page still open, run `D:\ACloud\.venv\Scripts\python.exe tools\probes\live_action_library_probe.py --controller 1` at the same administrator level. Confirm `data/logs/live_action_library_probe.json` contains `"success": true`, matching A / RT / LS state, and reset/pause cleanup.
10. Close the total workbench. It should briefly show safe-release progress if needed, then close only after both controllers have been reset and paused. Confirm a mapped key is ordinary keyboard input again after the window and its owned Host have closed.

The Host does not install drivers silently and does not bypass anti-cheat. It uses standard Windows low-level hooks only to consume configured physical inputs while mapping is running, except mouse movement when the explicit native-movement toggle is enabled.
