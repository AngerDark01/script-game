# Unified Event Runtime Design

## Goal

Replace the parallel local, remote, and catalog event runtimes with one
composed event-workbench service built from reusable modules. Remove duplicate
event-definition parsing and keep the GUI as a presentation adapter.

The refactor must preserve the externally verified behavior recorded by Git
tag `known-good/event-runtime-2026-09-18`:

- one source device can broadcast an event to two peers independently;
- event actions reach Controller 1 and Controller 2 without state crossover;
- game input and skill execution remain usable;
- one failed peer does not block delivery to another peer.

## Design Principles

1. Event definitions have one normalized in-memory contract and one parser.
2. Event execution is independent from trigger, transport, persistence, GUI,
   and Host APIs.
3. Input and output integrations are adapters around explicit protocols.
4. State is scoped per controller and event source.
5. The current Host and LAN wire commands remain unchanged during this
   refactor.
6. Old runtime classes are removed after callers and tests migrate; no
   long-lived compatibility shells remain.

## Target Architecture

```text
events.json     routes.json       remote catalog
     |               |                  |
     v               v                  v
EventDefinitionRepository   EventRouteRepository
              \                /
               \              /
                v            v
                 EventRouter
                     |
                     v
             EventExecutionRuntime
             - session/controller 1
             - session/controller 2
                     |
                     v
               EventStateSink

Adapters around the core:

HotkeyTriggerSource ----> EventWorkbenchService <---- RemoteEventInbox
LanEventTransport <------ EventWorkbenchService ----> HostEventStateSink
CatalogSyncAdapter <----> EventWorkbenchService <---- EventWorkbenchPage
```

## Module Responsibilities

### Event definition repository

The repository owns loading, validating, normalizing, indexing, and saving
event definitions. It returns immutable or snapshot-style normalized
definitions containing tracks, steps, execution limits, loop policy, revision,
and ownership metadata.

Every consumer uses this repository. Local execution, remote execution,
catalog publication, remote catalog display, and the GUI must not construct
parallel `SimpleNamespace` definitions or parse track modes independently.

### Route repository and router

The route repository owns persistence and normalization of route records. The
router consumes a normalized trigger and returns dispatch commands:

- local execution for one or both controllers;
- remote delivery for one or more explicitly selected peers;
- no dispatch for an invalid or disabled route.

It does not poll Windows keys, start sessions, contact LAN peers, or write Host
state.

### Event execution runtime

The runtime owns one independent `EventSession` per controller. Its public
operations are start, receive remote dispatch, tick, cancel, and snapshot. A
tick returns controller-addressed event state; it performs no device IO.

The runtime receives definition snapshots from the repository so an event
already running is not silently mutated when the user edits its source
configuration.

### Boundary adapters

- `HotkeyTriggerSource` converts Windows key transitions into normalized
  trigger events.
- `RemoteEventInbox` drains LAN events, validates deadline/catalog identity,
  and emits normalized dispatches.
- `HostEventStateSink` writes `event.state` and `event.clear` while preserving
  controller, source, and TTL semantics.
- `LanEventTransport` publishes catalogs and sends events independently per
  peer using the existing `sync.share.*` commands.
- `CatalogSyncAdapter` exchanges catalogs without consuming the event inbox.

These adapters are replaceable and independently testable. Only adapters may
access Win32, named pipes, Host commands, or LAN commands.

### Event workbench service

`EventWorkbenchService` is the composition root for the event workbench. It
owns repositories, the execution runtime, adapters, background lifecycle, and
thread-safe status snapshots. Its UI-facing commands include:

- load and save definitions/routes;
- start and stop local trigger monitoring;
- start and stop remote event reception;
- send an explicit remote event;
- read runtime/catalog status;
- close all workers idempotently.

The service is usable without PySide and accepts injected clocks, clients, and
trigger/output adapters for tests.

### Event workbench page

`EventWorkbenchPage` receives an `EventWorkbenchService`. It owns widgets,
editing buffers, validation feedback, status presentation, and timers used to
refresh the view. It does not read/write JSON directly, create transport
clients, or construct background runtimes.

## Lifecycle And Failure Behavior

- Start and stop operations are idempotent.
- Every worker reports errors through a status snapshot instead of terminating
  unrelated workers.
- Stopping the service clears only the event sources owned by that service.
- A failed peer is recorded independently and does not abort later peer sends.
- Expired remote events are rejected before a session starts.
- Catalog synchronization uses its dedicated drain and never consumes event
  commands.
- Editing configuration does not mutate a currently running event session.

## Compatibility Boundary

The following protocol commands and payload meanings remain unchanged:

- `event.state`
- `event.clear`
- `sync.status`
- `sync.share.event`
- `sync.share.drain`
- `sync.share.catalog`
- `sync.share.catalog_drain`

The C# Host, controller merge algorithm, source TTL behavior, and LAN wire
format are outside this refactor unless a focused test proves a necessary
correction.

## Migration Strategy

1. Add characterization tests for current event parsing, local execution,
   remote reception, fanout isolation, controller separation, and GUI service
   interaction.
2. Introduce normalized definition and route repositories and migrate all
   parsing callers.
3. Introduce the pure execution runtime and state-sink interface.
4. Extract hotkey, Host, LAN inbox, LAN transport, and catalog adapters.
5. Compose them in `EventWorkbenchService` and migrate the GUI.
6. Delete `LocalEventRuntime`, `RemoteEventRuntime`, and
   `EventCatalogRuntime`; update imports and tests.
7. Run focused Python tests, Host/LAN tests that do not start real sync, and
   compare behavior with the known-good tag.

## Verification

Automated verification must cover:

- one parser produces identical local and remote execution definitions;
- Controller 1 and Controller 2 sessions progress independently;
- local and remote dispatch use the same execution runtime;
- remote deadline and catalog identity validation;
- A -> B/C fanout continues after one peer fails;
- event state uses the correct controller/source/TTL and clears only that
  source;
- catalog drain cannot steal event messages;
- GUI constructs no legacy runtime and performs no direct JSON or Host/LAN IO;
- service stop is idempotent and neutralizes owned output.

No automated test may send real input or start a real network synchronization
session. Final real-device regression is compared against
`known-good/event-runtime-2026-09-18` after the code-level checks pass.
