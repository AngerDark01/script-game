# Torchlight Portal Feature Architecture

## Ownership

`features/torchlight/portal/` is a Torchlight-specific business feature. It owns
the trained/curated Portal evidence, Torchlight configuration, approach and
interaction policy, completion policy, diagnostics, and packaged assets.

It may compose stable capabilities from `auto_modules.core`, but no core module
may import this package or branch on the `portal` event type.

## Public composition surface

`PortalEventDefinition` is the registration boundary used by
`features/torchlight/composition.py`:

```python
event_type = "portal"
display_name = "Portal"

def default_config(self) -> dict: ...
def config_schema(self) -> dict: ...
def create_detector(self, config): ...
def create_handler(self, config): ...
```

The schema also owns its `compact` and `summary` display hints. Generic event UI
only interprets those neutral hints and never lists Portal parameter names.

## Module boundaries

```text
definition.py
  -> config.py
  -> minimap_detector.py
       -> minimap_detection/        mode dispatch, diagnostics, hit conversion
       -> minimap_feature_matcher/  blue-body feature matching
       -> minimap_shape_color/      shape/color evidence and scoring
  -> handler/
       -> movement.py               approach and interaction radii
       -> interaction.py            click/key policy and pre-action evidence
       -> completion.py             wait/complete/fail actions
       -> diagnostics.py            feature-local state logging
  -> completion_detector.py         teleport completion evidence
  -> environment_signature.py       before/after minimap comparison
  -> main_view_confirmer.py         Torchlight full-view glow evidence
  -> assets.py                       resources/games/torchlight paths
```

The detector emits generic `EventDetection` values. The handler emits generic
event actions/intents. Navigation, localization, pathfinding, scheduling,
controller output, and device/network effects remain outside this feature.

## Runtime flow

1. The Torchlight composition root registers `PortalEventDefinition`.
2. The generic event runtime requests the definition's defaults and schema.
3. `PortalMinimapDetector` converts Torchlight minimap evidence into a generic
   detection with domain-neutral navigation metadata.
4. Generic stabilization, memory, scheduling, and navigation select the task.
5. `PortalEventHandler` applies Torchlight approach/interaction/completion
   policy and returns generic actions.
6. Dedicated UI/input adapters render overlays or execute the resulting intent.

## Safety and tests

Pure detector, handler, config, and completion checks are tested without real
input. Real mouse, keyboard, virtual-gamepad, Host, or LAN effects remain
opt-in and must not be triggered by imports, probes, or unit tests.
