# Portal Event Architecture

## Package Role

`core/events/types/portal` is the first concrete event package. It should prove the event system can support:

- Minimap detection.
- Global position stabilization.
- Movement toward event target.
- Main-view confirmation.
- Interaction by click/key.
- Teleport completion detection.
- Cooldown and related-task cleanup.

## Verified Package Interface

`PortalEventDefinition` is the only intended public entrypoint:

```python
event_type = "portal"
display_name = "Portal"

def default_config(self) -> dict:
    return PortalEventConfig().to_dict()

def config_schema(self) -> dict:
    ...

def create_detector(self, config):
    return PortalMinimapDetector(PortalEventConfig.from_dict(config))

def create_handler(self, config):
    return PortalEventHandler(PortalEventConfig.from_dict(config))
```

This is a clean package boundary. The rest of the application should register `PortalEventDefinition`, not import the detector/handler directly except for probes/tests.

## Current Module Map

| Module | Current role | Refactor lens |
| --- | --- | --- |
| `definition.py` | Portal event definition and factories. | Should be the only registration surface. |
| `config.py` | Portal config dataclass. | Good candidate for typed config adapter. |
| `assets.py` | Portal asset paths. | Keep as package-local adapter. |
| `minimap_detector.py` | Detector that selects detection mode. | May be too mixed: mode dispatch, template loading, feature matching, shape-color matching. |
| `minimap_feature_matcher.py` | Blue portal-body feature matcher. | Reusable detector component. |
| `minimap_shape_color_matcher.py` | Shape+color matcher. | Algorithm-heavy component; should be documented at function level. |
| `main_view_confirmer.py` | Blue glow main-view confirmer. | Reusable confirmer component. |
| `handler.py` | Portal event execution state machine. | Candidate for state-machine extraction and hook support. |

## Detector Architecture

`PortalMinimapDetector.detect()` currently does all of this:

1. Normalize incoming config to `PortalEventConfig`.
2. Refresh feature templates if HSV signature changed.
3. Validate `tick.raw_minimap_frame` and template availability.
4. Select detector mode:
   - `feature`
   - `feature_then_template`
   - `shape_color`
   - `template`
5. Run selected algorithm:
   - feature matcher,
   - shape+color matcher,
   - generic template matcher fallback.
6. Log no-hit diagnostics.
7. Apply `_portal_color_check()` as a final acceptance filter.
8. Convert hits into generic `EventDetection`.
9. Log best hit summary.

This file is a mode-dispatch adapter, not the place for detector algorithms.

Target split:

```text
minimap_detector.py             # EventDetector adapter only
minimap_detection_modes.py      # feature/template/shape_color mode strategy
minimap_hit_filter.py           # final color check and hit -> EventDetection
minimap_feature_matcher.py      # keep algorithm component
minimap_shape_color_matcher.py  # keep algorithm component
```

Proposed interface:

```python
class PortalMinimapDetectionStrategy:
    def detect(self, frame, config, templates, scales) -> list[PortalHit]: ...

def hit_to_detection(hit, frame, tick, config, source: str) -> EventDetection | None: ...
```

## Desired Package Boundaries

```text
PortalEventDefinition
    ├── creates PortalMinimapDetector
    │       ├── feature matcher
    │       ├── shape-color matcher
    │       └── template matcher
    └── creates PortalEventHandler
            ├── approach/move request
            ├── main-view confirmation
            ├── click/key interaction
            └── completion/fail state
```

## Reusable Algorithm Components

### `minimap_feature_matcher.py`

Role: match portal by blue/cyan body pixels extracted from templates and frame.

Algorithm summary:

1. `portal_blue_mask()` converts BGR/gray image to HSV and thresholds hue/saturation/value.
2. `build_feature_templates()` converts loaded template images into binary blue masks and drops templates with too few blue pixels.
3. `match_portal_features()` creates the frame blue mask, runs scaled template matching on binary masks, collects response peaks, filters by blue pixel count, scores `mask_score * 0.86 + density_score * 0.14`, and merges nearby hits.
4. `merge_feature_hits()` keeps top-scoring non-duplicate hits by center distance.

This is a good reusable detector component.

### `minimap_shape_color_matcher.py`

Role: stricter portal recognition using blue body, white/gray outer ring, combined shape, edge, and color similarity.

Algorithm summary:

1. Build frame masks:
   - blue portal body mask,
   - low-saturation high-value outer mask excluding blue,
   - combined shape mask,
   - Canny edge mask.
2. For every template and scale, prepare equivalent blue/outer/shape/edge template masks.
3. Compute combined response:
   - blue mask response weight 0.30,
   - outer mask response weight 0.24,
   - shape mask response weight 0.24,
   - edge response weight 0.12,
   - color response weight 0.10.
4. Collect response peaks with local suppression.
5. Evaluate each candidate by F1-like mask scores, HSV color distance, and optional signature score.
6. Reject by score, blue shape, outer shape, combined shape, blue pixel range, and outer pixel minimum.
7. Merge top accepted/rejected candidates by center radius.

This is algorithm-heavy but already isolated. It should get focused tests before any refactor.

### `main_view_confirmer.py`

Role: confirm portal-like blue/purple glow in full game view.

Algorithm summary:

1. `build_blue_glow_mask()` thresholds cyan, blue, and violet HSV ranges.
2. Morphological open/close/dilate cleans the glow mask.
3. `detect_portal_candidates()` finds contours, filters by area, bbox ratio, min size, aspect, circularity, and glow ratio, then scores candidates.
4. `is_strict_portal_candidate()` applies stricter acceptance thresholds from JSON params.

Currently this confirmer is not directly wired in `PortalEventHandler.update()`; the handler relies on distance, key press, relocation, position/environment change, and known-exit checks. If main-view confirmation is desired before interaction, it should be added as a handler phase or hook, not hidden in navigation code.

## Handler State Machine

`PortalEventHandler` is a real state machine but encoded as string state plus several timestamp/signature fields.

Current states:

```text
move_near_event
  ├── if player missing -> WAIT
  ├── if distance > arrival_radius -> MOVE_TO portal
  ├── if distance > interact_radius -> MOVE_TO portal with force_repeat_click
  └── else -> align_on_portal

align_on_portal
  ├── first entry -> MOVE_TO portal with force_click_target
  ├── wait portal_point_click_wait_ms
  └── then -> interact

interact
  ├── record interaction time/player/signature
  ├── press D
  └── -> wait_result

wait_result
  ├── wait post_interact_wait_ms
  ├── if known exit reached -> COMPLETE teleport
  ├── if player moved teleport_min_distance -> COMPLETE teleport
  ├── if minimap environment signature changed -> COMPLETE teleport
  ├── if timeout -> FAIL
  └── otherwise WAIT with force_relocalize metadata
```

Target split:

```text
handler.py                  # EventHandler adapter
handler_state.py             # PortalHandlerState enum/dataclass
completion_detector.py       # known-exit / position-change / environment-change checks
environment_signature.py     # minimap signature extraction/difference
interaction_policy.py        # key/click interaction decision
```

Proposed state model:

```python
class PortalHandlerPhase(str, Enum):
    MOVE_NEAR_EVENT = "move_near_event"
    ALIGN_ON_PORTAL = "align_on_portal"
    INTERACT = "interact"
    WAIT_RESULT = "wait_result"

@dataclass
class PortalHandlerRuntime:
    phase: PortalHandlerPhase
    last_interact_ms: int | None = None
    interact_pos: tuple[int, int] | None = None
    interact_signature: np.ndarray | None = None
    portal_point_click_ms: int | None = None
    teleport_relocalize_requested: bool = False
```

This makes tests and hooks much easier.

## Hook Candidates

Portal-specific hook points that should not be hard-coded into navigation:

- `on_candidate_detected(candidate, mode)`
- `on_candidate_rejected(candidate, reason)`
- `on_arrival_radius_entered(task)`
- `on_main_view_confirmed(candidate)`
- `on_interaction_requested(action)`
- `on_teleport_detected(completion_signal)`
- `on_exit_portal_suppressed(task)`

Mapping to generic hooks:

| Portal need | Generic hook location |
| --- | --- |
| Candidate detected/rejected | Event monitor or detector hook: `on_detections`, plus detector-local debug hook if detailed rejection reasons are needed. |
| Stable portal task created | Event memory hook: `on_task_created`, `on_task_confirmed`. |
| Event selected for navigation | Navigation task hook: `after_task_selection`. |
| Approach released | Navigation event-approach hook: `before_event_handler` / `on_event_approach_released`. |
| Handler phase changed | Event runner/handler hook: `on_handler_action` or package-local hook. |
| Teleport completed | Event runner hook: `on_task_completed`; memory hook for teleport session completion. |

## Large-File Candidates

- `minimap_shape_color_matcher.py` at 390 lines: algorithm-heavy, likely needs detailed algorithm documentation before splitting.
- `handler.py` at 311 lines: state-machine candidate; split only after states and transitions are verified.
- `minimap_detector.py` at 279 lines: mode dispatch candidate.

Priority:

1. Extract handler state enum/runtime dataclass first. This is small and improves tests.
2. Extract completion detection from `handler.py`.
3. Extract detector mode strategy from `minimap_detector.py`.
4. Add tests around feature and shape-color matcher acceptance/rejection before touching algorithm internals.

## Config Boundary

`PortalEventConfig` is typed and useful. The schema in `PortalEventDefinition.config_schema()` is long but appropriate for GUI generation.

Refactor opportunity:

```text
config.py
  PortalEventConfig
  portal_config_schema()

definition.py
  delegates config_schema() to portal_config_schema()
```

This avoids keeping a large schema literal in the definition class.

## Round Status

Status: partial. Definition, config, assets, minimap detector, feature matcher, shape-color matcher, main-view confirmer, and handler were read.

Next read target:

- mapping/localization core: `core/stitcher_core.py`, `core/recognizer_optimized.py`, `core/navigation_core.py`, `core/pathfinder.py`.
