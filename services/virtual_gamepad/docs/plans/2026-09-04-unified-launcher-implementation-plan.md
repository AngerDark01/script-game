# Unified Virtual Gamepad Launcher Implementation Plan

## Goal

Create `启动 Virtual Gamepad.exe` at the module root so a double-click launches
the elevated host and visible UI together.

## Architecture Overview

A small .NET 8 WinExe owns only startup coordination. Its manifest requests
administrator rights. It checks the existing named pipe, starts the compiled
host only if needed, waits for readiness, then starts the UI with the correct
`PYTHONPATH`. Errors appear in a native Windows dialog.

## Tech Stack

- C# / .NET 8 Windows executable
- Existing named pipe: `AutoModules.VirtualGamepad.v1`
- Existing .NET host and Python 3.12/PySide6 UI
- xUnit for launcher path and command construction tests

### Task 1: Add launcher path resolution tests

Files:

- `host/tests/VirtualGamepadLauncher.Tests/LauncherPathsTests.cs`
- `host/tests/VirtualGamepadLauncher.Tests/VirtualGamepadLauncher.Tests.csproj`

Test the module-root calculation and priority-order runtime selection before
creating processes:

```csharp
[Fact]
public void FindsWorkspaceRuntimeBeforePathFallback()
{
    var paths = new LauncherPaths("D:\\ACloud\\auto_modules\\virtual_gamepad");
    Assert.Equal("D:\\ACloud\\dotnet-sdk2\\dotnet.exe", paths.DotnetCandidates().First());
}
```

Verify failure before implementation:

```powershell
& 'D:\ACloud\dotnet-sdk2\dotnet.exe' test host/tests/VirtualGamepadLauncher.Tests/VirtualGamepadLauncher.Tests.csproj --no-restore
# Expected: build fails because LauncherPaths does not yet exist
```

Commit: `test: define unified launcher path resolution`

### Task 2: Implement the startup coordinator

Files:

- `launcher/src/VirtualGamepadLauncher/LauncherPaths.cs`
- `launcher/src/VirtualGamepadLauncher/LauncherCoordinator.cs`
- `launcher/src/VirtualGamepadLauncher/Program.cs`

Implement `EnsureHostReady()` as: pipe exists -> return; otherwise start
`dotnet exec VirtualGamepadHost.dll`; poll the pipe for up to five seconds;
throw a descriptive exception on failure. Implement `OpenUi()` with
`pythonw.exe -m virtual_gamepad_ui.main` and the module's UI/client roots in
`PYTHONPATH`.

Verify:

```powershell
& 'D:\ACloud\dotnet-sdk2\dotnet.exe' test host/tests/VirtualGamepadLauncher.Tests/VirtualGamepadLauncher.Tests.csproj --no-restore
# Expected: all LauncherPaths tests pass
```

Commit: `feat: add unified gamepad launcher coordinator`

### Task 3: Add UAC manifest, build target, and module-root entry point

Files:

- `launcher/src/VirtualGamepadLauncher/VirtualGamepadLauncher.csproj`
- `launcher/src/VirtualGamepadLauncher/app.manifest`
- `launcher/VirtualGamepadLauncher.sln`
- `启动 Virtual Gamepad.exe` (generated, ignored by Git)

Configure a `WinExe` with `requireAdministrator` and publish/copy its output to
the module root as the user-facing executable. `Program.cs` catches all startup
exceptions and displays the error with `MessageBox`.

Verify:

```powershell
& 'D:\ACloud\dotnet-sdk2\dotnet.exe' build launcher/src/VirtualGamepadLauncher/VirtualGamepadLauncher.csproj --configuration Release
Test-Path '.\启动 Virtual Gamepad.exe'
# Expected: True
```

Commit: `feat: ship one-click virtual gamepad launcher`

### Task 4: Real launch and handoff verification

Files:

- `README.md`
- `docs/acceptance.md`

Confirm the EXE requests UAC, a single host owns the named pipe, the visible
`Virtual Gamepad` UI opens, and the host reports two controller slots. Document
the root EXE as the normal user entry point.

Verify:

```powershell
Start-Process '.\启动 Virtual Gamepad.exe'
# Expected: UAC, then one host and one UI window
```

Commit: `docs: document one-click gamepad startup`
