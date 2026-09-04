# Desktop OCR-to-Action Mapping Proof — Implementation Plan

## Goal

Build and test a generic pipeline that turns one OCR `TargetDetection` from a
desktop screenshot into a validated physical-screen `MappedPoint`, then gives
that point to a device-independent mouse double-click adapter.

## Architecture overview

```text
DesktopFrameSource -> FrameContext(FULL_SCREEN)
  -> injected OcrProvider -> ProviderBackedOcrDetector -> TargetDetection
  -> DesktopCoordinateMapper -> MappedPoint(PHYSICAL_SCREEN)
  -> MouseActionAdapter -> ActionResult
```

- Perception continues to own OCR and target selection only.
- `core.spatial` owns pure geometry, transform creation, and point validation.
- `core.actions` owns generic action DTOs and a mouse implementation behind a
  narrow protocol.
- `workflows.desktop_ocr_action_proof` owns only demonstration configuration,
  safety gates, reporting, and composition.
- The live action path is opt-in (`execute=True`); tests and default CLI behavior
  remain dry-run.

## Stack

- Python 3.12, `unittest`, NumPy/OpenCV baseline.
- Existing `rapidocr-onnxruntime==1.4.4` optional dependency for live OCR.
- Existing Win32 `InputDriver` only as the production mouse backend; tests use a
  fake protocol implementation.

## Task 1 — Spatial mapping DTOs and transform derivation

**Files**

- Add `core/spatial/desktop_mapping.py`
- Add `tests/test_desktop_coordinate_mapping.py`
- Update `core/spatial/__init__.py`

**Test first**

```python
def test_frame_center_maps_by_scale_and_desktop_offset(self):
    mapper = DesktopCoordinateMapper(
        source_size=(1920, 1080),
        destination=ScreenGeometry(left=-1920, top=0, width=3840, height=2160),
    )
    mapped = mapper.map_point(Point2D(960, 540), CoordinateSpace.FULL_SCREEN)
    self.assertEqual(Point2D(0, 1080), mapped.destination_point)
    self.assertEqual(2.0, mapped.metadata["scale_x"])
```

**Implementation contract**

```python
@dataclass(frozen=True)
class ScreenGeometry:
    left: float
    top: float
    width: float
    height: float
    dpi_scale_x: float = 1.0
    dpi_scale_y: float = 1.0

@dataclass(frozen=True)
class MappedPoint:
    source_point: Point2D
    source_space: CoordinateSpace
    destination_point: Point2D
    destination_space: CoordinateSpace
    metadata: Mapping[str, Any]

class DesktopCoordinateMapper:
    def __init__(self, *, source_size: tuple[int, int], destination: ScreenGeometry) -> None: ...
    def map_point(self, point: Point2D, source_space: CoordinateSpace) -> MappedPoint: ...
```

The mapper accepts only `CoordinateSpace.FULL_SCREEN`, computes independent
scale factors from source image dimensions to physical destination dimensions,
adds destination origin, rejects non-finite/off-image/out-of-destination points,
and returns immutable diagnostic evidence. It does no I/O.

**Verify**

```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_desktop_coordinate_mapping
# Expected: all identity, scale, offset, coordinate-space, and bounds tests pass.
```

**Commit:** `feat: add explicit desktop coordinate mapping`

## Task 2 — Physical desktop geometry and whole-desktop frame source

**Files**

- Add `core/platform/desktop_frame_source.py`
- Add `tests/test_desktop_frame_source.py`
- Update `core/platform/__init__.py` if it exports capture helpers

**Test first**

```python
def test_build_frame_context_preserves_full_screen_size_and_geometry(self):
    source = DesktopFrameSource(capture_backend=fake_capture, geometry_provider=fake_geometry)
    frame, geometry = source.capture()
    self.assertEqual(CoordinateSpace.FULL_SCREEN, frame.coordinate_space)
    self.assertEqual((1920, 1080, 3), frame.image.shape)
    self.assertEqual(1920, geometry.width)
```

**Implementation contract**

```python
class DesktopGeometryProvider(Protocol):
    def current_geometry(self) -> ScreenGeometry: ...

class DesktopFrameSource:
    def __init__(self, *, capture_backend: Callable[[ScreenGeometry], Any], geometry_provider: DesktopGeometryProvider) -> None: ...
    def capture(self) -> tuple[FrameContext, ScreenGeometry]: ...
```

The Windows provider reads virtual-screen geometry with Win32 metrics so
negative origins and multiple screens remain representable. It marks the Python
process DPI-aware before reading metrics where possible, captures the same
physical rectangle, verifies image dimensions are non-empty, and emits a
`FrameContext(FULL_SCREEN)`. The proof supports one primary desktop first but
its DTO must retain the full rectangle.

**Verify**

```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_desktop_frame_source
# Expected: fake-provider tests pass without capturing the real screen.
```

**Commit:** `feat: add desktop frame and physical geometry source`

## Task 3 — Generic action DTOs and mouse adapter

**Files**

- Add `core/actions/models.py`
- Add `core/actions/mouse.py`
- Add `core/actions/__init__.py`
- Add `tests/test_mouse_action_adapter.py`

**Test first**

```python
def test_double_click_moves_then_sends_two_mouse_down_up_pairs(self):
    device = FakeMouseDevice()
    result = MouseActionAdapter(device).execute(ActionRequest.double_click(mapped_point, interval_ms=20))
    self.assertEqual([("move", 480, 270), ("down",), ("up",), ("down",), ("up",)], device.calls)
    self.assertTrue(result.executed)
```

**Implementation contract**

```python
class ActionKind(StrEnum):
    MOVE = "move"
    DOUBLE_CLICK = "double_click"

@dataclass(frozen=True)
class ActionRequest:
    kind: ActionKind
    point: MappedPoint
    interval_ms: int = 80

class MouseDevice(Protocol):
    def move_to(self, x: int, y: int) -> bool | None: ...
    def mouse_down(self, button: str = "left") -> None: ...
    def mouse_up(self, button: str = "left") -> None: ...

class MouseActionAdapter:
    def execute(self, request: ActionRequest) -> ActionResult: ...
```

The adapter requires `PHYSICAL_SCREEN`, rounds only after mapping validation,
calls move once, makes zero clicks for `MOVE`, and makes exactly two left
down/up pairs for `DOUBLE_CLICK`. It does not clamp, select windows, or accept
OCR/detection objects.

**Verify**

```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_mouse_action_adapter
# Expected: fake-device ordering, invalid-space rejection, and move-only tests pass.
```

**Commit:** `feat: add generic mapped-point mouse actions`

## Task 4 — Safe composed desktop proof workflow

**Files**

- Add `workflows/desktop_ocr_action_proof.py`
- Add `tests/test_desktop_ocr_action_proof.py`

**Test first**

```python
def test_multiple_exact_text_hits_return_a_report_without_action(self):
    report = workflow.run(target_text="梦之形", execute=True)
    self.assertEqual("ambiguous", report.status)
    self.assertFalse(fake_actions.requests)
```

**Implementation contract**

```python
@dataclass(frozen=True)
class DesktopProofReport:
    status: Literal["dry_run", "executed", "not_found", "ambiguous", "rejected"]
    frame_size: tuple[int, int]
    geometry: ScreenGeometry
    detection: TargetDetection | None
    mapped_point: MappedPoint | None
    action_result: ActionResult | None
    reason: str | None

class DesktopOcrActionProof:
    def run(self, *, target_text: str, execute: bool = False) -> DesktopProofReport: ...
```

The workflow captures once, invokes injected OCR through the existing adapter,
filters to exact matches above the requested confidence, refuses zero or multiple
matches, maps the candidate center, and returns a complete report. It calls the
action adapter only when `execute=True` and all gates pass. The workflow is the
only place where target text is supplied.

**Verify**

```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_desktop_ocr_action_proof
# Expected: no-hit, ambiguous, dry-run, successful-action, and mapper-rejection tests pass.
```

**Commit:** `feat: compose safe desktop OCR action proof`

## Task 5 — Real desktop dry run and explicitly requested live proof

**Files**

- Add `utils/run_desktop_ocr_action_proof.py`
- Update `tests/test_desktop_ocr_action_proof.py` with optional local integration guard
- Update `docs/PERCEPTION_ENGINE_CHECKPOINT.md`, `CODEBASE.md`, and `ITERATION_LOG.md`

**Implementation contract**

```powershell
# First: report only, no cursor or click action.
D:\ACloud\.venv\Scripts\python.exe utils\run_desktop_ocr_action_proof.py --text 梦之形

# Only after reviewing one unique report: requested actual action.
D:\ACloud\.venv\Scripts\python.exe utils\run_desktop_ocr_action_proof.py --text 梦之形 --execute
```

The CLI prints JSON-safe diagnostics: image width/height, physical geometry,
recognized bbox/center/confidence, affine scale and offset, mapped point, and
final action status. It obtains a live RapidOCR provider by explicit composition
with the installed model; no profile or generic package starts model download.

**Verify**

```powershell
# Automated regression suite
D:\ACloud\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*desktop*py"

# Real dry run: Expected one exact 梦之形 detection and no cursor movement.
D:\ACloud\.venv\Scripts\python.exe utils\run_desktop_ocr_action_proof.py --text 梦之形

# Live run: Expected one cursor move and exactly one double click at the reported mapped point.
D:\ACloud\.venv\Scripts\python.exe utils\run_desktop_ocr_action_proof.py --text 梦之形 --execute
```

**Commit:** `feat: verify desktop OCR coordinate action pipeline`
