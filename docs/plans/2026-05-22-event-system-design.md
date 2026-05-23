# Event System Design

## Goal
Add a modular event layer that continuously watches the raw minimap, queues enabled map events, temporarily takes over navigation to complete them, and then resumes normal route navigation.

## Core Principle
Event detection must use raw captures, not the post-processed localization masks. Localization intentionally removes colorful dynamic icons; event detection needs those icons.

## Runtime Flow
```text
Navigation loop
  -> capture raw minimap frame
  -> NavigationCore localizes player from processed features
  -> EventMonitor detects enabled event icons from raw minimap frame
  -> EventMemory stores confirmed events in global map coordinates
  -> EventScheduler selects one active event or keeps normal route navigation
  -> AutoNavigator walks to the active target
  -> EventHandler executes event-specific interaction
  -> completed event is removed, then normal navigation resumes
```

## Module Boundaries
`EventMonitor`
Reads the raw minimap frame and asks enabled event detectors for candidates.

`EventDetector`
One detector per event type. It owns only visual detection, for example `PortalMinimapDetector`.

`EventMemory`
Keeps confirmed events after they leave the current minimap view. It handles deduplication, expiry, completion, and map overlay data.

`EventScheduler`
Chooses which event to handle first using event priority, distance, age, and enabled strategy config.

`EventHandler`
One handler per event type. It owns event execution, for example navigating near a portal, confirming the real portal on the main game view, clicking it, and deciding completion.

`EventConfig`
Stores per-map or per-strategy enabled event types and per-event thresholds. Disabled events are not detected and cannot enter the queue.

## Portal Event v1
Detection source:
- Raw minimap capture.
- Template matching against one or more saved portal minimap icon templates.
- Multi-scale matching.
- Optional HSV prefilter for speed.
- 2-3 frame stability before confirmation.

Navigation target:
- Convert minimap-local event icon position to global map coordinates using current localized player position, current player-local minimap position, and `draw_scale`.

Execution:
- Pause normal route navigation.
- Navigate to the portal event global coordinate.
- Near the target, inspect the raw main game view.
- Confirm the large portal with HSV blue/purple segmentation plus circular/elliptical contour checks.
- Click the portal center or press the configured interaction key.
- Mark completed when interaction succeeds or the scene changes.

## Why Template Matching First
The minimap icon is a small, fixed UI asset. Template matching is easier to debug and maintain than YOLO for this first version. YOLO can be considered later only if event icon classes become numerous or highly variable.

## Probe Plan
Before integrating the event system, validate portal minimap icon matching with a standalone probe:
- Read `map_data/A1/config.json`.
- Capture the raw minimap rectangle.
- Load a local template image.
- Run multi-scale template matching.
- Save raw capture and annotated match debug images.
- Print best score and local minimap coordinates.

## Probe Result 2026-05-22
Environment:
- Map folder: `map_data/A1`.
- Capture geometry from config: DPR `1.5`, physical minimap rect `left=133, top=154, width=180, height=180`.
- Screenshot capture must run elevated/admin in the same permission level as the game; non-admin capture can return black frames.

Template assets:
- `assets/event_templates/portal/minimap/portal_minimap_01.png`.
- `assets/event_templates/portal/minimap/portal_minimap_02.png`.

Verified command:
```powershell
D:\ACloud\.venv\Scripts\python.exe utils\event_icon_probe.py --map-folder map_data\A1 --template assets\event_templates\portal\minimap\portal_minimap_01.png --template assets\event_templates\portal\minimap\portal_minimap_02.png --threshold 0.60 --top-k 10 --output-dir debug\event_probe\portal_match_assets_admin
```

Observed accepted matches:
- `portal_minimap_01`: score `0.9652`, center `(45, 61)`, size `32x32`.
- `portal_minimap_02`: score `0.9172`, center `(68, 87)`, size `32x32`.

Conclusion:
- Multi-template matching is viable for the first portal minimap detector.
- A detector should keep templates grouped per event type, then dedupe by local minimap center distance and require multi-frame stability before creating an event.
- The current template assets are promoted out of `debug/` and can be reused by the first `PortalMinimapDetector`.
