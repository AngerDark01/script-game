# OCR Provider Adapter Design

## Goal

Add a reusable OCR algorithm adapter that converts raw `OcrProvider` evidence into target-level `TargetDetection` values. The adapter must remain independent of a particular OCR package, game, GUI, input action, coordinate mapper, or workflow.

## Architecture

```text
TargetProfile algorithm parameters
  -> PerceptionEngine runtime factory override
       -> explicit OcrProvider.recognize(frame, provider_parameters)
       -> OcrSpan(text, bbox, coordinate_space, confidence, language, metadata)
       -> ProviderBackedOcrDetector text predicate and confidence filter
       -> TargetDetection
       -> existing runner / fusion / confirmation / selection stages
```

The provider knows only how to read text from a `FrameContext`. It returns raw spans and does not know `target_type`, selection policy, coordinate mapping, or actions. The adapter applies profile-configured matching and is the only layer that adds target semantics.

## API Contract

```python
class ProviderBackedOcrDetector:
    algorithm_id = "ocr"

    def __init__(
        self,
        *,
        target_type: str,
        provider: OcrProvider,
        parameters: Mapping[str, Any] | None = None,
    ) -> None: ...

    def detect(self, frame: FrameContext) -> list[TargetDetection]: ...


def create_ocr_detector(
    parameters: Mapping[str, Any],
    *,
    ocr_provider: OcrProvider | None = None,
) -> ProviderBackedOcrDetector: ...
```

`parameters` support these generic controls:

- `text_query`: required non-empty text or regular expression;
- `match_mode`: `exact` (default), `contains`, or `regex`;
- `case_sensitive`: `False` by default;
- `min_ocr_confidence`: `0.0` by default, bounded to `[0, 1]`;
- `max_results`: optional result cap; omitted or `0` returns all matching spans, while a positive value retains the strongest spans;
- `provider_parameters`: optional mapping forwarded unchanged as a defensive copy to `recognize()`.

Each matching span becomes one `TargetDetection` with the profile target type, its original bounding box and coordinate space, its center, OCR confidence, source `ocr`, frame capture time, text, and one `DetectionEvidence("ocr", ...)` item. Evidence records the normalized matching settings, language, and a defensive copy of raw span metadata.

## Failure and Compatibility Rules

1. The provider must expose callable `recognize(frame, parameters=None)`; otherwise construction raises `TypeError`.
2. Missing provider, empty query, unknown matching mode, invalid confidence bound, invalid `provider_parameters`, invalid regex, invalid result cap, non-iterable provider output, or a non-`OcrSpan` provider item raise clear errors.
3. Provider-raised errors propagate unchanged. The existing `DetectorRunner` records them per algorithm instance and continues other instances.
4. Provider objects remain runtime-only closures supplied through `PerceptionEngine.algorithm_factories`; profiles serialize just data parameters.
5. The default OCR descriptor remains `unavailable` because this project does not bundle an OCR backend. Existing template/color behavior and all legacy profile formats remain unchanged.

## TDD Slices

### Slice 1 — Adapter result contract

Create a failing test using an in-memory provider. Verify the provider receives the frame and an isolated copy of `provider_parameters`; exact matching emits one geometry-preserving OCR detection; a nonmatching span and a low-confidence span do not emit results.

### Slice 2 — Matching and validation boundaries

Add one failing behavior at a time for case-insensitive contains matching, regex matching, malformed regex, invalid provider/output, and provider error propagation. Implement only the smallest validation/filtering needed for each behavior.

### Slice 3 — Factory, runtime composition, and public surface

Add failing tests that `create_ocr_detector()` rejects a missing provider, accepts an explicit provider, `PerceptionEngine` invokes it via an `ocr` runtime factory override without serializing the provider, and the adapter is importable from `core.perception.algorithms`.

## Verification

```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_perception_ocr_adapter -v
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_perception_providers tests.test_perception_template_adapter tests.test_perception_algorithms tests.test_perception_engine tests.test_perception_stages -v
D:\ACloud\.venv\Scripts\python.exe -m compileall -q core/perception
git diff --check
```

No GUI, input, navigation, game workflow, OCR package installation, or real screen capture is in scope for this slice.
