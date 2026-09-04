# Desktop OCR-to-Action Mapping Proof Design

## Goal

Validate the reusable chain from visual target discovery to a real desktop input
point without coupling perception, coordinate mapping, or actions to a game or
to one desktop icon. The first configuration will find the visible text
`梦之形` on the current Windows desktop with OCR, map its recognized position to
the physical screen, and double-click its center to open it.

The proof answers one architecture question: can a `TargetDetection` produced
from a screenshot safely and transparently become an input action on the same
display?

## Boundaries

```text
Capture source
  -> FrameContext(image, coordinate_space, capture metadata)
  -> recognition provider + detector
  -> TargetDetection(bbox, center, confidence, coordinate_space)
  -> coordinate mapper
  -> MappedPoint(physical screen coordinate, transform evidence)
  -> action adapter
  -> ActionResult
```

### Perception

The OCR provider receives a frame and returns text evidence. The OCR detector
applies the configured literal `梦之形` predicate for this demonstration and
returns a regular `TargetDetection`. It knows nothing about Windows input,
screen scale, or double-clicking.

### Mapping

The mapper accepts an input source coordinate space and image dimensions,
compares them with the currently detected physical desktop rectangle, and maps
a target center to a `MappedPoint`. The first proof supports an explicit
identity-or-scale affine mapping between a captured desktop image and the
physical primary-screen coordinate space. It reports source dimensions,
destination dimensions, scale factors, transform type, and final point.

It must reject a mismatched coordinate space, empty dimensions, non-finite
coordinates, or a mapped point outside the destination desktop bounds. It does
not capture, recognize, move a cursor, or click.

### Actions

The action adapter receives an already mapped point and a generic action
request. The initial action set is only `move` and `double_click`, but the
request is device-agnostic: a future mouse, keyboard, virtual controller, or
gamepad adapter can consume a mapped point without changing the mapper.

The mouse implementation does not accept images, OCR text, profiles, or target
selection policy. It validates its `MappedPoint`, moves the cursor, applies the
requested click count/interval, and returns an action result with the executed
coordinates and timestamps.

### Composition / safety

Only the desktop proof composes the three modules. It treats `梦之形`, exact
text matching, the primary desktop, and `double_click` as test configuration.
It will refuse to act when:

- OCR finds no exact match;
- more than one exact match remains after selection;
- confidence is below the proof threshold;
- the mapped point lies outside the detected screen rectangle;
- the capture screen dimensions and destination geometry cannot form a valid
  transform.

Before executing, it prints or returns a `DesktopProofReport` containing the
frame size, detected bounding box, original center, mapping scales, mapped
physical point, and action result. Tests can run in dry-run mode; the requested
live run is the only mode that enables a real double-click.

## Schema

```text
FrameContext
  image: ndarray
  coordinate_space: FULL_SCREEN
  captured_at_ms: int

TargetDetection
  target_type: str
  bbox / center: source-frame pixels
  confidence: float
  coordinate_space: FULL_SCREEN

ScreenGeometry
  coordinate_space: PHYSICAL_SCREEN
  left, top, width, height: float
  dpi_scale_x, dpi_scale_y: float

MappedPoint
  source_point: (float, float)
  source_space: CoordinateSpace
  destination_point: (float, float)
  destination_space: CoordinateSpace
  metadata: mapping transform evidence

ActionRequest
  kind: move | double_click
  point: MappedPoint
  interval_ms: int

ActionResult
  executed: bool
  point: (float, float)
  device_id: str
  started_at_ms / completed_at_ms: int
  metadata: mapping and backend evidence
```

`FULL_SCREEN` may initially refer to a source image whose physical desktop is
also the destination. The explicit geometry remains necessary because the
capture backend, Python process DPI-awareness setting, multiple displays, and
future game-window crops can make source and destination pixels differ.

## Verification sequence

1. Unit-test the mapper with identity, scale, offset, invalid-space, and
   out-of-bounds cases.
2. Unit-test the mouse action adapter with a fake backend. Assert it refuses
   invalid points and never receives a `TargetDetection` directly.
3. Test the composed pipeline with a fake OCR provider, exact text matching,
   fake screen geometry, and fake mouse adapter. Assert zero/multiple/noisy
   results do not action.
4. Capture the real desktop and run OCR in dry-run mode. Inspect the returned
   detection box, source center, mapped physical point, and dimensions.
5. With one unambiguous `梦之形` detection, execute the requested live mouse
   move and double-click, then report the exact action result.

## Explicit non-goals

- No hard-coded icon coordinates or screen resolution.
- No OCR model switch per action; provider composition remains explicit.
- No game-window calibration, multi-display routing, controller movement, or
  generalized macro library in this proof.
- No embedding of desktop text, app names, or click actions inside the generic
  perception, spatial, or action libraries.
