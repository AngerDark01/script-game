# Dual virtual Xbox controller design

## Goal

Expose two independent Xbox 360 XInput devices from one elevated
`VirtualGamepadHost` process. Each device has an independent keyboard/mouse
mapping and run state so one game can receive controller input for two roles.

## Confirmed behaviour

- Controller 1 and controller 2 are separate virtual Xbox 360 devices.
- Each controller has its own binding profile and can use entirely different
  physical keys and mouse inputs.
- A physical source explicitly bound in both profiles drives both controllers
  concurrently. This is how one keyboard can control two roles.
- `F7` toggles controller 1 only.
- `F8` toggles controller 2 only.
- `F9` is a global emergency reset: pause both controllers, release every
  virtual button/axis/trigger, and stop suppressing mapped physical input.
- A paused controller neither receives mapping input nor suppresses its
  bindings. The other controller can continue running.
- Closing the UI pauses both controllers before disconnecting.

## Host design

### Controller slots

Replace the single store/mapping/backend/report loop with two controller slots:

```text
ControllerSlot 1: StateStore + MappingEngine + ViGEm Xbox 360 target + ReportLoop
ControllerSlot 2: StateStore + MappingEngine + ViGEm Xbox 360 target + ReportLoop
```

One ViGEm client creates two separate Xbox 360 targets. Each target submits
only its own slot state. Startup and shutdown create/neutralise/disconnect both
devices in a deterministic order.

### Physical input fan-out

There remains one low-level keyboard/mouse hook. For every physical input, it
dispatches to each slot whose run state is `Running`. An input is consumed only
when at least one running slot has that input in its binding profile. This
preserves normal keyboard/mouse behaviour whenever neither active profile uses
the source.

### Safety

Each slot owns a `SafetyController`. F7 toggles slot 1, F8 toggles slot 2, and
F9 calls `EmergencyReset()` on both. All disposal, pipe disconnection, driver
failure and UI close paths send neutral reports for both slots.

## Pipe protocol

Commands that target device state or mappings accept a `controller` number:

```json
{ "type": "set_config", "payload": { "controller": 2, "config": { "bindings": [] } } }
```

Affected commands: `get_state`, `get_config`, `set_config`, `start`, `pause`,
`reset`, `button`, `set_axis`, `set_trigger`, `set_state`, and `heartbeat`.

For compatibility, omitted `controller` means controller 1. `get_status`
returns a compact status for both slots, while retaining the existing top-level
controller-1 fields for old clients.

## Configuration

Profiles are saved independently:

```text
configs/controller-1.json
configs/controller-2.json
```

The profile format stays compatible with the existing binding format. The
defaults use F7 for controller 1 and F8 for controller 2. F9 remains global and
is not configurable per controller.

## UI

The UI has a compact two-controller status strip at the top and a controller
selector for `Controller 1 (F7)` and `Controller 2 (F8)`. Selecting a slot
shows that slot's virtual-controller diagram and independent binding editor.
Both slot statuses remain visible at all times, including device connectivity,
running/paused state, and current virtual input activity.

The existing keyboard dropdown and mouse dropdown remain separate. Mapping
edits apply immediately to only the selected slot. UI close pauses both slots.

## Acceptance checks

1. `joy.cpl` shows two Xbox 360 controllers while the host is running.
2. Controller 1 and controller 2 accept independently issued button/axis
   commands without state bleed.
3. F7 changes only controller 1 run state; F8 changes only controller 2.
4. A shared binding drives both controllers; an unshared binding drives only
   the configured controller.
5. Pausing controller 1 restores its bindings while controller 2 mappings
   remain active.
6. F9, UI close, host shutdown, and a driver failure neutralise both devices
   and restore physical input.
