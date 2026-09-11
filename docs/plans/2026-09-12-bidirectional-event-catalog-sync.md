# 双向事件目录同步与远程触发开发计划

## Goal

让 A、B 两台已配对设备各自维护自己的事件定义，并通过事件共享通道互相读取、选择和触发；事件只能由所属设备编辑，执行设备使用收到的事件版本驱动本机虚拟手柄。

## Architecture Overview

- 每个事件拥有稳定 `id`、`owner_device_id`、`revision`、`updated_at`、`deleted`。
- 本机事件保存在 `configs/events/events.json`，远程事件保存在 `configs/events/remote_events.json`。
- LAN `share` 会话同步目录摘要；目录版本变化时同步完整事件定义。
- `sync.share.event` 使用事件 ID、事件版本和目标 Controller，不再只依赖名称。
- 事件所有者可修改/删除自己的事件；接收端只读。
- A/B 都能发送：B 创建的事件可以发给 A，A 创建的事件可以发给 B。
- Xbox 输入只在事件执行设备本地生成，发送设备不需要启动 Xbox 映射。

## Tech Stack

- Python 3.12：事件模型、事件运行时、工作台 UI、配置迁移。
- PySide6：事件库、远程事件只读库、路由和同步状态 UI。
- C# .NET 8：LAN 配对会话、目录摘要/详情传输、版本校验。
- 现有 Named Pipe、LiteNetLib、ViGEm Host 和 EventSession 继续复用。

## Implementation Tasks

### Task 1: Git checkpoint and compatibility tests

Files: `docs/plans/...`, existing test directories.

Actions:

1. Create a rollback commit before changing protocol files.
2. Add migration fixtures containing old name-only events and routes.
3. Verify old local event tests still pass.

Command:

```powershell
git add .
git commit -m "checkpoint: before bidirectional event catalog sync"
```

Verification: existing Python compile checks and LAN tests remain green.

### Task 2: Add Python event identity and revision model

Files:

- `core/events/config_model.py`
- `core/events/config_io.py`
- `core/events/event_catalog.py` (new)
- `core/events/tests/test_event_catalog.py` (new)

Implement UUID identity, owner ID, revision, hash, tombstones, and migration from name-only JSON. Tests must cover stable IDs, owner-only mutation, revision increments, and deletion tombstones.

Verification:

```powershell
D:/ACloud/.venv/Scripts/python.exe -m unittest core.events.tests.test_event_catalog
```

Expected: all catalog model tests pass.

### Task 3: Add local and remote event stores

Files:

- `core/events/event_store.py` (new)
- `core/events/tests/test_event_store.py` (new)
- `core/runtime/local_event_runtime.py`
- `core/runtime/remote_event_runtime.py`

Implement local editable store and remote read-only cache. Runtime lookup must resolve both local and cached events by ID, while local name-only routes remain compatible.

Verification: store tests cover create/update/delete, remote read-only rejection, and lookup by ID; `compileall` passes.

### Task 4: Add LAN catalog summaries and event definitions

Files:

- `lan_input_sync/src/LanInputSync/LanSyncService.cs`
- `lan_input_sync/src/LanInputSync/LanSyncService.SharedData.cs`
- `lan_input_sync/tests/LanInputSync.Tests/CatalogSyncTests.cs` (new)

Add `sync.events.catalog.request`, `sync.events.catalog`, `sync.events.fetch`, `sync.events.data`, `sync.events.upsert`, and `sync.events.delete`. Catalog messages include device ID, catalog revision, event IDs, owner IDs, event revisions, hashes, and tombstones. Reject non-owner writes and stale revisions.

Verification:

```powershell
D:/ACloud/dotnet-sdk2/dotnet.exe test lan_input_sync/tests/LanInputSync.Tests/LanInputSync.Tests.csproj --no-restore
```

Expected: existing LAN tests plus catalog tests pass.

### Task 5: Exchange catalog automatically when a share session starts

Files:

- `lan_input_sync/src/LanInputSync/LanSyncService.Control.cs`
- `lan_input_sync/src/LanInputSync/LanSyncService.Transport.cs`
- `lan_input_sync/src/LanInputSync/LanSyncService.SharedData.cs`

On a data-only session becoming active, exchange catalog summaries and request only missing or stale definitions. Keep input, position, and event channels independently enabled.

Verification: loopback test confirms both peers receive each other's catalogs without enabling Controller 1/2 ownership.

### Task 6: Upgrade event trigger protocol to ID and revision

Files:

- `lan_input_sync/src/LanInputSync/LanSyncService.SharedData.cs`
- `core/runtime/remote_event_sender.py`
- `core/lan_follow/follow_transport.py`
- `lan_input_sync/tests/LanInputSync.Tests/LoopbackTests.cs`

Accept `eventId`, `eventRevision`, and `catalogRevision`; retain a temporary name fallback for old installations. Reject missing/stale definitions with explicit error codes. Test events created on either peer and delivered to the other.

### Task 7: Make both runtimes resolve synchronized events

Files:

- `core/runtime/local_event_runtime.py`
- `core/runtime/remote_event_runtime.py`
- `core/runtime/tests/test_bidirectional_event_runtime.py` (new)

Local runtime sends events to selected peers for routes targeting paired devices. Remote runtime resolves received event IDs from local or remote cache, validates revision, starts EventSession, and emits `event.state` to selected Controller 1/2.

Verification: fake-client tests assert the complete send/receive/state chain for Controller 1, Controller 2, and both.

### Task 8: Update event workbench data sources and permissions

Files:

- `gui/modes/events/workbench.py`
- `gui/modes/events/event_catalog_panel.py` (new if extraction is needed)
- `gui/modes/events/tests/test_workbench_catalog.py` (new)

Add local/remote event sections, owner labels, revision and sync state. Local events open in the editor; remote events are read-only but selectable in route and remote-send dropdowns. B-created events and A-created events appear symmetrically after synchronization.

### Task 9: Add event sync status to LAN panel

Files:

- `virtual_gamepad/ui/virtual_gamepad_ui/sync_panel.py`
- `virtual_gamepad/ui/tests/test_sync_panel.py`

Display event channel state, local/remote counts, catalog revisions, pending updates, last sync, and stale/conflict errors. Do not require Controller checkboxes for event-only channels.

### Task 10: Diagnostics and end-to-end tests

Files:

- `core/runtime/local_event_runtime.py`
- `core/runtime/remote_event_runtime.py`
- `virtual_gamepad/host/src/VirtualGamepadHost/Diagnostics/HostDiagnostics.cs`
- `docs/testing/bidirectional-event-sync.md` (new)

Add structured logs for catalog request/response/apply, trigger send/receive, revision validation, EventSession start, and `event.state`. Document A creates → B reads/triggers and B creates → A reads/triggers scenarios.

Verification: run Python compile checks, LAN tests, Host tests, and a real two-process loopback with the virtual Host.

### Task 11: Build and package

Files:

- `distribution/README.md` if packaging notes change.

Commands:

```powershell
D:/ACloud/.venv/Scripts/python.exe -m distribution.build --output D:/ACloud/auto_modules/build/bidirectional-events
D:/ACloud/auto_modules/build/bidirectional-events/python/python.exe -I -B D:/ACloud/auto_modules/build/bidirectional-events/app/smoke_check.py
build/installer-tools/InnoSetup/ISCC.exe /DPayloadDir=D:/ACloud/auto_modules/build/bidirectional-events /DOutputDir=D:/ACloud/auto_modules/dist /DAppVersion=0.2.0 installer/AutoModules.iss
```

Expected: smoke check passes and the installer contains the updated Python app, LAN Host, ViGEm prerequisite, and event catalog code.

## Checkpoints

- Checkpoint 1: model/store migration complete.
- Checkpoint 2: LAN catalog loopback complete.
- Checkpoint 3: bidirectional event trigger complete.
- Checkpoint 4: UI and diagnostics complete.
- Checkpoint 5: packaged installer smoke check complete.
