# Event Localization Stabilizer Design

## Goal

Events must not become map tasks from a single minimap offset. Detection only reports an icon position inside the current minimap frame. Localization uses the same wall registration that locates the player, then multiple registered frames are fused into one stable global event position.

## Lifecycle

1. Detection: each event detector returns local minimap candidates, confidence, source, and debug metadata.
2. Localization: the common stabilizer projects local candidates through the current frame registration.
3. Stabilization: samples are clustered by event type and global distance; only stable clusters become observations.
4. Trigger: memory creates or updates event tasks only from stable observations.
5. Execution and completion: handlers operate on the fixed task coordinate and decide completion, failure, cooldown, or ignore.

## Shared Contract

- `FrameRegistration` describes one minimap frame aligned to the global wall map.
- `EventDetection` is local-only and never contains a trusted global coordinate.
- `EventObservation` is stable/global and is the only input accepted by event memory.
- Event-specific code stays under `core/events/types/<event>/`; shared localization and clustering stays in `core/events/position_stabilizer.py`.

## Projection Rule

`frame_origin_global = player_global_pos - player_local_minimap_pos * draw_scale`

`event_global_pos = frame_origin_global + event_local_minimap_pos * draw_scale`

This replaces the old single-frame offset projector. The draw scale direction is explicit and consistent with navigation wall matching.
