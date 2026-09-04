# Legacy Chain Convergence: Implementation Plan

## Goal

Finish the usable compatibility chain without replacing proven minimap, Portal, Loot, navigation, or input behavior:

```text
legacy frame and recognizer
  -> MapFrameEvidence / LocalizationResult
  -> EventDetection or NavigationIntent
  -> typed navigation composition action
  -> ActionCommand or explicit map-movement request
  -> MotionController compatibility adapter
  -> existing mouse / keyboard backend
```

Portal and Loot retain their resource loading, detection rules, temporal policy, and handlers. Their outputs gain a reversible bridge to `TargetDetection` in `MINIMAP` space, which lets future generic perception composition use the same event positioning and task machinery.

## Task 1 — Complete generic primitive-action vocabulary

1. Add `ActionKind.CLICK` to the generic action contract and make it require `PointerTarget`.
2. Extend `MouseActionAdapter` with exactly-one-click behavior; keep `ActionRequest` compatibility limited to its existing move/double-click API.
3. Add a generic `physical_screen_point(x, y)` spatial constructor that returns an explicitly identity-mapped `MappedPoint` in `PHYSICAL_SCREEN` space.
4. Add isolated action/spatial tests for validation, a single click, and no regression to double-click behavior.

## Task 2 — Add the temporary MotionController action backend

1. Create `MotionControllerActionAdapter` under `core.input`, implementing `ActionAdapter` only for `CLICK` and one-key `KEY_CHORD` commands.
2. Convert the physical `PointerTarget` back to integer desktop coordinates and call existing `MotionController.click_screen_position()`; use `MotionController.press_key()` for keyboard commands.
3. Report an `ActionResult` without bypassing control enablement, focus policy, bottom-click behavior, or input backend selection.
4. Add fake-controller tests for enabled and disabled actions and rejection of non-primitive/map-domain targets.

## Task 3 — Replace direct navigation and hook dispatch with composition translation

1. Add immutable navigation composition actions: `MapMovementAction` for global-map direction requests and `PrimitiveNavigationAction` for `ActionCommand`.
2. Translate `MOVE_MAP` only to `MapMovementAction`; translate `CLICK_SCREEN` to `CLICK + PointerTarget(physical_screen_point(...))`; translate `PRESS_KEY` to a one-key `KEY_CHORD`.
3. Make `execute_navigation_intent()` execute the translated action through the temporary backend, retaining its status suffix and `record_intent_click()` timing.
4. Route event key hooks through the same command adapter.
5. Add tests that prove no map action is mistaken for a pointer command, current map-click method selection is preserved, and primitive commands preserve old side effects.

## Task 4 — Add the event-perception schema bridge

1. Create pure EventDetection ↔ TargetDetection conversion functions under `core.events`.
2. Preserve event type, confidence, timestamp, local minimap center, optional bbox/text, and copied metadata; use `CoordinateSpace.MINIMAP`.
3. Make conversion explicit about required event type when consuming a generic detection; reject non-minimap coordinates rather than silently projecting them.
4. Test lossless round trip and invalid coordinate-space rejection.

## Task 5 — Compose Portal and Loot detector output through the bridge

1. At the event-monitor boundary, normalize legacy Portal/Loot `EventDetection` lists through `TargetDetection` and back before stabilization/memory. This makes the bridge part of the running chain while preserving existing detectors and their return type.
2. Add a focused event-monitor regression proving detector object identity-relevant fields and event task behavior survive the bridge.
3. Do not place templates, HSV ranges, resource identifiers, pickup keys, or portal states in the generic adapter.

## Task 6 — Audit and document the full chain

1. Run all focused action, navigation, event, Portal, Loot, localization, and mapping tests.
2. Run full discovery and distinguish new failures from the recorded advanced-settings/pathfinder baseline.
3. Synchronize `CODEBASE.md`, `ITERATION_LOG.md`, and `PERCEPTION_ENGINE_CHECKPOINT.md` after each code slice.
4. Commit only the explicit action/event bridge files, tests, and architecture documentation. Do not push or include unrelated virtual-gamepad work.
