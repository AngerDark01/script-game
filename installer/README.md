# Native offline installer

`AutoModules.iss` consumes the payload built by `distribution/`. The install root is independent of the development workspace. The launcher must be published using `--self-contained true -r win-x64 -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true`. The launcher itself requests administrator permission and launches the bundled `python/pythonw.exe` visibly without a terminal window. No system Python or .NET runtime is required.

## Data and startup contract

- `app/main.py`: workbench entry point; Python paths are supplied by the bundled runtime, not inherited `PYTHONPATH` or `PYTHONHOME`.
- `host/VirtualGamepadHost.exe`: self-contained host; exported through `AUTO_MODULES_HOST_DIR`.
- `%LOCALAPPDATA%/AutoModules/Workbench`: writable data and working directory; exported through `AUTO_MODULES_DATA_DIR`. Explicit `AUTO_MODULES_DATA_DIR` overrides are supported for isolated tests. The launcher disables Python bytecode writes and clears inherited `QT_QPA_PLATFORM` so a development offscreen setting cannot hide the installed UI.
- `defaults/config.json` and `defaults/virtual_gamepad/configs/*.json`: seed only missing files.
- Configuration/profile seeding stages each file before a non-overwriting atomic rename, so failed copies cannot leave a truncated final configuration.
- `defaults/map_data/<map>`: seed each absent map directory atomically. Never restore missing files inside an existing edited map.
- No pairing identities, private keys, credentials or logs are seeded. Application uninstall does not remove writable user data or the shared ViGEmBus driver.

## Driver trust and installer flow

The main installer workflow, controls, tasks and prerequisite errors are localized in Simplified Chinese directly in the script (original project translations, no additional downloaded translation). Untranslated low-level Inno errors retain upstream English text. Before installation/upgrades, the launcher checks full executable paths for running instances of the installed Python UI, host and launcher, and asks the user to close them. It never terminates processes or treats similarly named programs in other directories as this installation.

Uninstall uses the same close/retry check before deleting program files. The checker excludes its own process ID so the installed launcher can perform this check. Silent uninstall cancels if applications are still active. If the installed checker executable is missing or broken, repair the installation before uninstalling; the uninstaller does not bypass its safety check.

The release pinned in source is Nefarius ViGEmBus 1.22.0, retrieved from:
https://github.com/nefarius/ViGEmBus/releases/download/v1.22.0/ViGEmBus_1.22.0_x64_x86_arm64.exe

SHA-256: `89220A7865076B342892F98865F3499FB7C4CFD673159E89D352C360FD014C6A`

Before executing it, the launcher verifies the pinned SHA-256, Windows Authenticode trust (including timestamp handling) and signer name `Nefarius Software Solutions e.U.`. Verification uses local certificate/cache state rather than requiring online revocation access, so offline setup is possible; an untrusted chain still fails closed. Installation uses the original signed executable with `/quiet /norestart /log`.

Before file installation, Inno runs the prerequisite check. An available bus is not reinstalled; a neutral virtual Xbox target is connected/disconnected to verify usability. A missing bus triggers the bundled official prerequisite. A broken/incompatible bus fails with diagnostics instead of blind replacement. Driver failure prevents a successful completion screen. Reboot-needed exit codes ask the user to restart and rerun setup, never force a reboot. The driver test briefly creates a neutral controller, so setup should run while games and the workbench are closed.

This project does not have its own code-signing certificate: Windows may show an unknown-publisher warning for the application/setup. That is distinct from the required official driver signature. ViGEmBus upstream is retired; the installer deliberately pins the tested release instead of following an untrusted updater.

## Diagnostic CLI

CLI modes are non-interactive (apart from Windows UAC on the executable). Log: `%LOCALAPPDATA%/AutoModules/Workbench/logs/launcher.log`.

| Mode | Effect |
| --- | --- |
| `--self-test` | Validate payload paths and seed missing data; no UI, network or driver calls |
| `--check-running <install-root>` | Refuse updates with exit code `30` while executables from that installation are running |
| `--check-driver` | Connect to ViGEmBus; no virtual target |
| `--verify-controller` | Temporarily connect/disconnect one neutral Xbox target |
| `--verify-prerequisite` | Verify bundled prerequisite hash, trust and publisher only |
| `--ensure-driver` | Ensure driver is usable, installing verified prerequisite only if absent |

Exit codes: `0` ready/success; `1` unexpected launcher error; `2` invalid arguments; `10` bus absent; `11` prerequisite verification failure; `20` driver install failure; `21` bus/controller probe failure; `3010` restart required. The original driver installer exit code is logged separately. No command swallows physical input or enables gamepad mappings.

## Build and tests

```powershell
dotnet test installer/tests/Installer.Tests.csproj
dotnet publish installer/launcher/AutoModulesLauncher.csproj -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -o <payload-root>
ISCC.exe /DPayloadDir=<payload-root> /DOutputDir=<output> /DAppVersion=0.1.0 installer/AutoModules.iss
```
