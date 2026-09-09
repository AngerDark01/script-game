# LAN input sync implementation

## Goal
Implement the approved independent LAN controller module and integrate it into the existing host and workbench without intercepting receiver keyboard input.

## Architecture Overview
One independently testable .NET library initially uses Contracts/Core/Transport/Security folders. Host owns the ViGEm adapter. TLS controls authenticated sessions; LiteNetLib transports authenticated state and ordered button transitions. UI uses local pipe management commands. All outputs start disabled.

## Tech Stack
.NET 8, LiteNetLib 2.1.4, SslStream, AES-GCM, PySide6, xUnit, unittest.

## Execution units
1. Record design checkpoint, create feature branches preserving existing changes. Add independent library contracts and failing core tests. Files: lan_input_sync/src/LanInputSync/{LanInputSync.csproj,Contracts.cs}, lan_input_sync/tests/LanInputSync.Tests/{LanInputSync.Tests.csproj,SyncTests.cs}.
2. Implement network/core/security library behind ILanSyncService, device discovery, explicit pairing confirmation, persistent device identity/trust, per-peer routing, deadlines and bounded queues. Files: lan_input_sync/src/LanInputSync/{LanSyncService.cs,Security.cs,Wire.cs,RemoteState.cs}. Verify real loopback TLS/UDP plus expiry and short-button sequences before integrating.
3. Add host adapter using a single effective state per report. Files: virtual_gamepad/host/src/VirtualGamepadHost/{VirtualGamepadHost.csproj,Runtime/ControllerRegistry.cs,Runtime/HostComposition.cs,Protocol/CommandRouter.cs,Integration/LanSyncAdapter.cs}. Remote ownership bypasses local stores and rejects local writes. Unit tests cover independent slots, pause/reset/F9 and no physical suppression under remote ownership.
4. Add independent PySide sync widget and embed as a subpage. Files: virtual_gamepad/ui/virtual_gamepad_ui/{sync_panel.py,gamepad_page.py}, virtual_gamepad/ui/tests/test_sync_panel.py. Network work uses a separate pipe worker, status polling never blocks GUI; shutdown disables sync via existing cleanup flow.
5. Spec review then quality review; fix findings, run full host/module and focused UI regression tests, build Release artifacts without forcibly restarting user sessions. Record test evidence and two-PC tests still requiring another device.

## Verification commands
```powershell
& 'D:\ACloud\dotnet-sdk2\dotnet.exe' test 'D:\ACloud\auto_modules\lan_input_sync\tests\LanInputSync.Tests\LanInputSync.Tests.csproj'
& 'D:\ACloud\dotnet-sdk2\dotnet.exe' test 'D:\ACloud\auto_modules\virtual_gamepad\host\tests\VirtualGamepadHost.Tests\VirtualGamepadHost.Tests.csproj'
$env:PYTHONPATH = 'D:\ACloud\auto_modules;D:\ACloud\auto_modules\virtual_gamepad\ui;D:\ACloud\auto_modules\virtual_gamepad\client\python'
$env:QT_QPA_PLATFORM = 'offscreen'
& 'D:\ACloud\.venv\Scripts\python.exe' -m unittest discover -s 'D:\ACloud\auto_modules\virtual_gamepad\ui\tests'
```
Expected: all relevant tests pass. A loopback result is not evidence of real LAN/game latency. No controller profile edits or unrelated files in feature commits.
