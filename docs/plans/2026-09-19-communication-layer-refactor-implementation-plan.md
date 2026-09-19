# 通用通信层重构实施计划

## Goal

建立一个可复用、可持久信任、自动重连、一个 peer 一个物理 session、多业务能力复用的通信层；迁移跟随和事件业务，同时为未来地图模块预留插拔接口但不实现地图同步。

## Architecture Overview

- `core/communication` 只定义 Peer、Session、Capability、Topic、QoS、消息 envelope 和 transport 端口。
- `application/communication` 创建一个进程级 `CommunicationManager`，统一连接、重连、能力租约和消息分发。
- `adapters/host` 只负责 Python 与 VirtualGamepadHost 的协议适配。
- `services/lan_input_sync` 从 `DataOnly`/互斥 mode 升级为能力集合和 session multiplexer。
- `FollowService`、`EventWorkbenchService` 和未来地图功能只能申请能力、发布消息和订阅 topic。
- 已配对 peer 的信任关系持久化；普通断线和进程重启自动恢复已授权能力；手动断开、手动停止、忘记设备或急停会清除自动恢复资格。
- 地图只保留 `map.*` 扩展接口和未知消息隔离测试，不实现地图传输业务。

## Tech Stack

- Python 3.11+、pytest、现有 `src/auto_modules` 包布局。
- C# / .NET 8 项目位于 `services/virtual_gamepad` 和 `services/lan_input_sync`。
- Python 到 Host：Windows Named Pipe + JSON line protocol。
- Host 到 peer：TLS control session + encrypted LiteNetLib UDP lanes。
- 纯模块测试使用 fake transport；LAN 测试使用 loopback；真实设备测试显式 opt-in。

## Task 1: Add Communication Contracts

Files:

- `src/auto_modules/core/communication/__init__.py`
- `src/auto_modules/core/communication/contracts.py`
- `src/auto_modules/core/communication/messages.py`
- `src/auto_modules/core/communication/qos.py`
- `tests/test_communication_contracts.py`

Steps:

1. Write failing tests for `PeerId`, `SessionId`, `Capability`, `Topic`, `DeliveryMode`, `MessageEnvelope` and TTL/deadline validation.
2. Define immutable, device-neutral contracts. Contracts must not import `adapters`, `application`, `ui` or C# protocol details.
3. Define capabilities for `input.send`, `input.receive`, `position.publish`, `position.subscribe`, `event.publish`, `event.subscribe`, `catalog.publish`, `catalog.subscribe`, `map.publish`, and `map.subscribe`.
4. Define QoS values for latest/sequenced, reliable-ordered, and versioned-resource messages.
5. Add compatibility constructors for the existing `SharedPosition` and `SharedEvent` fields without importing `core.lan_follow` from the new module.

Verify:

```powershell
python -m pytest -q tests/test_communication_contracts.py
# Expected: all contract and validation tests pass
```

Commit: `feat: add communication contracts and qos model`

## Task 2: Add Persistent Trust Store Ports and Tests

Files:

- `src/auto_modules/application/communication/trust_store.py`
- `src/auto_modules/application/communication/__init__.py`
- `tests/test_communication_trust_store.py`
- `data/communication/.gitkeep`

Steps:

1. Write failing tests for first-save, reload, peer lookup, certificate fingerprint mismatch, revoke, forget, and capability preference persistence.
2. Implement a file-backed store using `data_root() / "communication"`; never use the current working directory.
3. Store only non-secret metadata in JSON: device id, peer id, certificate fingerprint, address, port, last seen, and capability preferences.
4. Separate trust records, revocations, and desired capability recovery state.
5. Make writes atomic through a temporary file and replace operation; malformed files must fail closed and return a diagnostic error.

Verify:

```powershell
python -m pytest -q tests/test_communication_trust_store.py
# Expected: persistence, revoke, forget, and fingerprint rejection tests pass
```

Commit: `feat: persist communication trust and recovery preferences`

## Task 3: Add Process-Scoped Communication Manager

Files:

- `src/auto_modules/application/communication/manager.py`
- `src/auto_modules/application/communication/sessions.py`
- `src/auto_modules/application/communication/leases.py`
- `src/auto_modules/application/communication/dispatcher.py`
- `src/auto_modules/application/communication/reconnect.py`
- `tests/test_communication_manager.py`
- `tests/test_communication_dispatcher.py`

Steps:

1. Write failing fake-transport tests proving two business features requesting the same peer receive one physical connection.
2. Implement `CommunicationManager` as an injected runtime object, not a process-global singleton.
3. Key sessions by peer id and reject duplicate physical session creation inside the manager.
4. Implement capability leases with reference counting; releasing one lease must not close a session used by another feature.
5. Implement one inbound reader/dispatcher per session; business subscribers receive filtered messages and never call a shared drain endpoint.
6. Implement session generation fencing so stale reconnect tasks and stale messages cannot reactivate a manually stopped session.
7. Add recovery policy: ordinary disconnect and process restart restore previously authorized capabilities; manual disconnect, manual stop, forget, and emergency stop clear recovery state.

Verify:

```powershell
python -m pytest -q tests/test_communication_manager.py tests/test_communication_dispatcher.py
# Expected: shared-session, lease, fan-out, stale-generation, and recovery tests pass
```

Commit: `feat: add shared communication manager and dispatcher`

## Task 4: Adapt Host Transport to the Manager

Files:

- `src/auto_modules/adapters/host/communication_adapter.py`
- `src/auto_modules/adapters/virtual_gamepad/virtual_gamepad_client.py`
- `src/auto_modules/adapters/host/follow_transport.py`
- `src/auto_modules/adapters/host/event_bridge.py`
- `tests/test_host_communication_adapter.py`

Steps:

1. Write failing tests for request/response correlation, connection close, command errors, and event delivery through a fake `VirtualGamepadClient`.
2. Move shared Host connection ownership into `communication_adapter.py` while keeping the existing client protocol behavior.
3. Make `FollowTransport` and `HostEventBridge` thin business field adapters over the manager; they must not call `connect`, `close`, or drain shared queues directly.
4. Keep `VirtualGamepadClient` available for isolated program-output workers, but prevent it from being used to create independent LAN sessions.
5. Preserve the existing `program.*` path for actor workers; only `sync.*` ownership moves to the manager.

Verify:

```powershell
python -m pytest -q tests/test_host_communication_adapter.py tests/test_event_host_bridge.py tests/test_follow_transport.py
# Expected: adapter contract tests pass without real Host startup
```

Commit: `refactor: route host communication through shared manager`

## Task 5: Add Persistent Auto-Reconnect to the C# LAN Service

Files:

- `services/lan_input_sync/src/LanInputSync/IdentityStore.cs`
- `services/lan_input_sync/src/LanInputSync/PeerTrustStore.cs`
- `services/lan_input_sync/src/LanInputSync/LanSyncService.Control.cs`
- `services/lan_input_sync/src/LanInputSync/LanSyncService.cs`
- `services/lan_input_sync/tests/LanInputSync.Tests/TrustStoreTests.cs`
- `services/lan_input_sync/tests/LanInputSync.Tests/LoopbackTests.cs`

Steps:

1. Write failing C# tests proving first pairing requires the code, a trusted peer reconnects without the code, and a changed certificate is rejected.
2. Separate trust persistence from active session state. Keep the existing one-use code and fingerprint confirmation only for enrollment or explicit certificate replacement.
3. Add reconnect scheduling with bounded exponential backoff and session-generation cancellation.
4. Persist the last known private address/port and peer certificate fingerprint; never persist active session keys.
5. Add explicit `forget`, `revoke`, `manual disconnect`, and `emergency stop` fences that disable automatic recovery.

Verify:

```powershell
dotnet test services/lan_input_sync/tests/LanInputSync.Tests/LanInputSync.Tests.csproj
# Expected: trust, reconnect, certificate-change, and fencing tests pass
```

Commit: `feat: persist LAN trust and reconnect trusted peers`

## Task 6: Replace DataOnly With Session Capabilities

Files:

- `services/lan_input_sync/src/LanInputSync/SessionCapabilities.cs`
- `services/lan_input_sync/src/LanInputSync/LanSyncService.Control.cs`
- `services/lan_input_sync/src/LanInputSync/LanSyncService.SharedData.cs`
- `services/lan_input_sync/src/LanInputSync/LanSyncService.Transport.cs`
- `services/lan_input_sync/src/LanInputSync/Contracts.cs`
- `services/virtual_gamepad/host/src/VirtualGamepadHost/Runtime/ControllerRegistry.cs`
- `services/virtual_gamepad/host/src/VirtualGamepadHost/Protocol/CommandRouter.cs`
- `services/lan_input_sync/tests/LanInputSync.Tests/LoopbackTests.cs`
- `services/virtual_gamepad/host/tests/VirtualGamepadHost.Tests/LanIntegrationTests.cs`

Steps:

1. Write failing loopback tests for one peer session carrying input, position, event, and catalog capabilities concurrently.
2. Replace the session-wide `DataOnly` boolean with a capability set negotiated during session start or update.
3. Map legacy `start` and `start-data` commands to compatibility capability sets during migration.
4. Reject packets that are not authorized by the session capability set.
5. Preserve Controller ownership, grants, input watchdog, neutralization, and emergency-stop behavior.
6. Keep event/catalog/position queues logically separate while using one physical session.

Verify:

```powershell
dotnet test services/lan_input_sync/tests/LanInputSync.Tests/LanInputSync.Tests.csproj
dotnet test services/virtual_gamepad/host/tests/VirtualGamepadHost.Tests/VirtualGamepadHost.Tests.csproj
# Expected: existing LAN/Host tests plus concurrent-capability tests pass
```

Commit: `feat: multiplex LAN capabilities within one peer session`

## Task 7: Migrate Follow and Event Workbench to Shared Communication

Files:

- `src/auto_modules/application/follow/service.py`
- `src/auto_modules/application/event_workbench/service.py`
- `src/auto_modules/ui/modes/follow/page.py`
- `src/auto_modules/ui/modes/events/workbench.py`
- `src/auto_modules/ui/virtual_gamepad/sync_panel.py`
- `src/auto_modules/ui/composition/services.py`
- `tests/test_follow_service.py`
- `tests/test_event_workbench_service.py`
- `tests/test_event_host_bridge.py`

Steps:

1. Write failing tests proving FollowService and EventWorkbenchService use one injected manager and do not create separate LAN sessions.
2. Inject the process-scoped manager from UI/bootstrap composition.
3. Change follow to acquire `position.publish`, `position.subscribe`, and `event.subscribe` leases.
4. Change event workbench to acquire `event.publish`, `event.subscribe`, `catalog.publish`, and `catalog.subscribe` leases.
5. Change UI start/stop actions to enable or release capabilities instead of starting dedicated links.
6. Keep program-output actor workers on their isolated `program.*` Host path; do not make worker processes own LAN sessions.
7. Remove direct calls to `sync.share.drain` from business services.

Verify:

```powershell
python -m pytest -q tests/test_follow_service.py tests/test_event_workbench_service.py tests/test_event_host_bridge.py
# Expected: follow/event behavior passes with one fake shared session
```

Commit: `refactor: migrate follow and events to shared communication runtime`

## Task 8: Reserve Map Capability Without Implementing Map Sync

Files:

- `src/auto_modules/core/communication/contracts.py`
- `src/auto_modules/core/communication/messages.py`
- `src/auto_modules/application/communication/dispatcher.py`
- `services/lan_input_sync/src/LanInputSync/SessionCapabilities.cs`
- `tests/test_communication_map_extension.py`

Steps:

1. Write failing tests proving `map.publish` and `map.subscribe` can be declared as capabilities and unknown map messages do not affect position/event/input dispatch.
2. Define versioned-resource message envelope fields: `resourceType`, `resourceId`, `version`, `manifestHash`, `chunkIndex`, and `chunkCount`.
3. Do not implement storage, chunk transfer, map merge, or map UI.
4. Verify that future map messages can be rejected or ignored without closing unrelated sessions.

Verify:

```powershell
python -m pytest -q tests/test_communication_map_extension.py
# Expected: extension-point and topic-isolation tests pass
```

Commit: `feat: reserve versioned map communication extension point`

## Task 9: Documentation, Diagnostics, and Compatibility Cleanup

Files:

- `ARCHITECTURE_GUIDE.md`
- `CODEBASE.md`
- `ITERATION_LOG.md`
- `README.md`
- `services/lan_input_sync/README.md`
- `services/lan_input_sync/docs/protocol-v1.md`
- `docs/plans/2026-09-19-communication-layer-refactor-draft.md`

Steps:

1. Write documentation checks or focused tests for the documented command and capability names.
2. Document one-connection/multiple-capability semantics, persistent trust, reconnect rules, manual disconnect behavior, and Controller ownership.
3. Document the compatibility period for legacy `sync.start`, `sync.start-data`, and `sync.share.*` commands.
4. Record that maps are an extension point only and are not implemented by this refactor.
5. Run the CodeGraph index sync and update CODEBASE/ITERATION_LOG according to the project ontology process.

Verify:

```powershell
python -m compileall -q src tests tools packaging
python -m pytest -q
# Expected: all migration-related tests pass; pre-existing Pathfinder/environment failures remain separately identified
```

Commit: `docs: document multiplexed communication architecture`

## Execution Notes

- Do not use `git reset --hard` or `git checkout --`.
- Preserve `pre-reorg/2026-09-18`.
- Keep real input, real Host, real LAN, and game verification opt-in.
- Run Python tests after each Python task and C# tests after each C# task.
- The current machine may lack the .NET SDK; when unavailable, record the exact blocker and run all available Python/fake/loopback checks.
- Each task must be completed and committed before starting the next task.
