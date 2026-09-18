# Unified Virtual Gamepad Launcher Design

## Goal

Provide one user-facing executable at the root of the independent virtual
gamepad module. Double-clicking it starts the elevated C# host and the PySide6
mapping UI as one operation.

## User contract

- Entry point: `启动 Virtual Gamepad.exe` in the module root.
- It requests UAC once because the host and UI must operate at the same high
  integrity level as an elevated game.
- It reuses a reachable host pipe instead of starting a second host.
- It waits for the host pipe before opening the UI.
- It reports failures in a Windows dialog; it never exits silently.
- Closing the UI does not force-close the host. The UI still sends the global
  F9-equivalent emergency reset on close.

## Implementation

The launcher is a small .NET 8 Windows executable with a `requireAdministrator`
manifest. It locates its module root from its own executable directory, then
uses:

- `D:\ACloud\dotnet-sdk2\dotnet.exe` or a locally discoverable `dotnet.exe`
  to run the compiled host DLL;
- `D:\ACloud\.venv\Scripts\pythonw.exe` (falling back to `python.exe`) to run
  `virtual_gamepad_ui.main`;
- the existing `AutoModules.VirtualGamepad.v1` pipe as the readiness contract.

It builds as a Windows GUI process, so ordinary success is quiet; only errors
are shown to the user. The existing Python launcher remains for development
and automated tests, while the new EXE is the normal manual entry point.

## Safety

The launcher does not install drivers, bypass game protections, send game
inputs, or terminate an already-running host. If an existing host is found it
is reused. If a fresh host fails to expose its pipe within five seconds, the
launcher reports the exact action the user can take.
