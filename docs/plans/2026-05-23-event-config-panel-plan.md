# Event Config Panel Plan

## Goal
Expose portal interaction-distance settings in the event manager UI and save them into the current map's `event_config.json`.

## Architecture Overview
Use each event definition's `config_schema()` as the source of truth. `EventManagerDialog` renders a small parameter editor for the selected complete event and writes changes into `EventSystemConfig.events[event_type]`; existing `save_requested` persists the config.

## Tasks
1. Add `interact_radius`, `cooldown_ms`, and `type_cooldown_ms` to the portal schema.
2. Add a schema-driven editor panel to `gui/dialogs/event_manager_dialog.py`.
3. Wire row selection to load the selected event config.
4. On parameter edit, update in-memory config, refresh summary, and emit `config_changed`.
5. Verify with `py_compile` and import checks only.
