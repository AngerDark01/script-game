# Perception Provider Seams Design

## Goal

Define the replaceable resource/back-end boundary below generic perception algorithms, so frames, template assets, OCR engines, and local-feature backends can be selected or reported unavailable without adding game rules or mandatory dependencies.

## Selected architecture

```text
application composition / GUI configuration
  -> ProviderRegistry
       -> FrameSource            -> FrameContext
       -> TemplateResourceProvider -> TemplateResource
       -> OcrProvider            -> OcrSpan[]
       -> FeatureBackend         -> FeatureMatch[]
  -> algorithm adapter (P4)
  -> TargetDetection
  -> PerceptionEngine (P2)
```

Providers supply raw data or raw backend evidence. Only algorithms/adapters turn that information into a `TargetDetection`, apply target profile parameters, and choose confidence semantics. This keeps the output contract consistent regardless of whether recognition comes from a fixed screenshot asset, OCR, template, feature, or a future ML backend.

`ProviderRegistry` is deliberately an object registry, not a generic factory registry: each capability has a different type-safe Protocol. It exposes descriptors to the front end, resolves by provider ID with an optional expected capability, and returns the registered implementation object to a typed adapter.

## Contracts and errors

| Contract | Raw output | Does not do |
|---|---|---|
| `FrameSource.capture()` | `FrameContext` | target detection or action |
| `TemplateResourceProvider.load(id)` | `TemplateResource` | template matching |
| `OcrProvider.recognize(frame, parameters)` | `OcrSpan` sequence | target selection/action |
| `FeatureBackend.match(frame, resource, parameters)` | `FeatureMatch` sequence | target profile policy |

Resolution errors are explicit and non-overlapping:

- `UnknownProviderError`: no descriptor is registered for the requested ID.
- `ProviderCapabilityMismatchError`: provider exists but does not serve the requested capability.
- `ProviderUnavailableError`: provider is declared unavailable or has no installed implementation.
- `ProviderRegistrationError`: invalid/duplicate registration, including available or experimental descriptor without an implementation.

`available`, `experimental`, and `unavailable` are configuration/discovery states. The first two require an implementation at registry-registration time; `unavailable` has no implementation and remains discoverable so the front end can explain what is missing.

## Atomic TDD tasks

### Task 1 — Provider contract DTOs

Files:

- `core/perception/providers/__init__.py`
- `core/perception/providers/contracts.py`
- `tests/test_perception_providers.py`

Write failing imports and assertions for:

```python
descriptor = ProviderDescriptor("ocr.local", "Local OCR", ProviderCapability.OCR, status="unavailable")
span = OcrSpan("Enter", BoundingBox(2, 3, 20, 8), CoordinateSpace.GAME_WINDOW, 0.91)
resource = TemplateResource("assets/device", image=object())

assert descriptor.to_dict()["capability"] == "ocr"
assert span.text == "Enter"
assert resource.resource_id == "assets/device"
```

Implement immutable DTOs, Protocols, and errors without importing OpenCV, a screen-capture package, an OCR package, or a feature package.

Verify:

```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_perception_providers.ProviderContractTests -v
```

### Task 2 — Capability-safe registry

Files:

- `core/perception/providers/registry.py`
- `core/perception/providers/__init__.py`
- `tests/test_perception_providers.py`

Write failing tests for resolve, descriptor filtering, defensive descriptor metadata, unknown ID, mismatch, unavailable, and invalid available-without-implementation registration.

Implement:

```python
registry = ProviderRegistry()
registry.register(descriptor, provider)
provider = registry.resolve("ocr.local", ProviderCapability.OCR)
```

`resolve()` returns the same registered provider object; it does not invoke it, inspect frame data, or convert output types.

Verify:

```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_perception_providers -v
```

### Task 3 — Discoverable default provider catalog

Files:

- `core/perception/providers/builtins.py`
- `core/perception/providers/__init__.py`
- `tests/test_perception_providers.py`

Write a failing test requiring `create_default_provider_registry()` to expose unavailable descriptors for `frame.screen`, `template.resource`, `ocr.default`, and `feature.default`, with no implementation falsely resolved.

Implement only the discovery catalog. No operating-system capture, disk resource reader, OCR package, or feature implementation is introduced in P3.

Verify:

```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_perception_providers tests.test_perception_engine -v
D:\ACloud\.venv\Scripts\python.exe -m compileall -q core/perception
```

### Task 4 — P3 release checkpoint

Files:

- `docs/PERCEPTION_ENGINE_CHECKPOINT.md`
- `ITERATION_LOG.md`
- `CODEBASE.md`

Run all perception tests, package import smoke tests, and `git diff --check`. Record any full-suite import failures as pre-existing only after confirming they are unrelated. Commit only the provider package, provider tests, and perception documentation:

```text
feat: add perception provider seams
```

## Non-goals

- Do not change `TemplateDetector` path compatibility in P3; P4 adapts it to `TemplateResourceProvider`.
- Do not add a hard OCR/ML dependency.
- Do not attach providers to GUI controls before P6.
- Do not attach providers to Portal, Loot, minimap, mapping, input, or PoE workflows before P7/P8.
