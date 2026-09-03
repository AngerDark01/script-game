# Template Resource Adapter Design

## Goal

接入独立的 `TemplateResourceProvider`，让模板识别算法通过资源 ID 获取图像，同时保留当前数组输入和 `template_path` 兼容行为。

## Architecture Overview

```text
TargetProfile.parameters
  -> algorithm factory
       -> TemplateResourceProvider.load(resource_id)
       -> TemplateResource.image
       -> TemplateDetector(target_type, template=array, parameters)
       -> existing multi-scale / mask / edge matching
       -> TargetDetection
```

资源 provider 只负责“根据稳定 ID 返回原始模板资源”；它不做灰度化、缩放、边缘匹配、阈值判断、NMS、置信度计算或目标选择。`TemplateDetector` 继续是纯匹配算法，接收 `np.ndarray` 时行为不变。适配器负责 provider 错误上下文和资源 ID 传递，不复制匹配实现。

默认算法 registry 继续支持：

- `template` + `template`：既有内存数组入口；
- `template` + `template_path`：既有文件路径入口；
- `template` + `template_resource_id` + 显式 `TemplateResourceProvider`：新的通用入口。

未提供 provider 时，使用资源 ID 的配置必须得到明确的 `ValueError`；不存在资源时保留 provider 自己的错误，并在 adapter 中添加 provider ID/resource ID 上下文。数组和路径入口不能偷偷要求 provider。

## Selected approach

选择独立 adapter，而不是让 `TemplateDetector` 持有 provider，也不是让 `AlgorithmRegistry` 全局管理资源读取。这样算法底层仍可单独测试，provider 可被内存 fixture、磁盘资源包、远程缓存或未来前端资源管理器替换。

## API contract

```python
class ProviderBackedTemplateDetector:
    def __init__(self, *, target_type, provider, resource_id, parameters=None): ...
    def detect(self, frame): ...  # delegates to TemplateDetector(array)
```

The adapter must:

1. validate `provider` exposes `load` and `resource_id` is non-empty;
2. call `provider.load(resource_id)` exactly once during construction;
3. require a returned `TemplateResource` and pass only `resource.image` to `TemplateDetector`;
4. preserve `TargetDetection` target type, coordinate space, evidence, confidence, and source from `TemplateDetector`;
5. allow provider errors to propagate as `ProviderError` subclasses with added context, never silently fall back to a path.

## Atomic TDD tasks

### Task 1 — Resource-backed adapter contract

Files:

- `core/perception/algorithms/template_adapter.py`
- `tests/test_perception_template_adapter.py`

Write a failing test using an in-memory provider:

```python
provider = MemoryTemplateProvider(TemplateResource("device", image=template))
detector = ProviderBackedTemplateDetector(
    target_type="map_device",
    provider=provider,
    resource_id="device",
    parameters={"threshold": 0.85},
)
result = detector.detect(frame)
assert result[0].target_type == "map_device"
assert provider.loaded_ids == ["device"]
```

Verify before implementation:

```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_perception_template_adapter -v
# Expected: ERROR because template_adapter.py does not exist.
```

Implement only the adapter and deterministic tests for provider call count, missing/invalid resource, and unchanged detection output. Do not modify the registry yet.

Commit: `feat: add template resource adapter`

### Task 2 — Factory composition with explicit provider context

Files:

- `core/perception/builtins.py`
- `core/perception/algorithms/base.py` only if descriptor metadata needs one new parameter kind
- `tests/test_perception_template_adapter.py`

Write a failing test for an explicit factory helper:

```python
detector = create_template_detector(
    {"target_type": "map_device", "template_resource_id": "device"},
    template_provider=provider,
)
```

Expected before implementation: `ImportError` or `TypeError` because the helper/provider argument does not exist.

Implement `create_template_detector(parameters, template_provider=None)`:

- if `template` or `template_path` exists, preserve the existing path/array construction;
- if `template_resource_id` exists, require `template_provider`, resolve it once through `ProviderBackedTemplateDetector`, and pass remaining parameters to the detector;
- if neither exists, raise the existing clear “template requires a resource” error;
- never accept both resource ID and path/array silently; raise a configuration `ValueError` for ambiguous input.

Keep `_create_template()` as a backward-compatible wrapper that calls this helper with no provider. Do not make the global `AlgorithmRegistry` know about provider objects.

Verify:

```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_perception_template_adapter tests.test_perception_algorithms -v
D:\ACloud\.venv\Scripts\python.exe -m compileall -q core/perception
```

Commit: `feat: compose template provider adapter`

### Task 3 — Engine/application composition seam

Files:

- `core/perception/engine.py`
- `tests/test_perception_template_adapter.py`

Write a failing test that supplies a provider-aware detector factory or adapter through an explicit engine composition hook, while asserting default `PerceptionEngine()` remains unchanged and does not require a provider.

Implement the smallest explicit composition seam (constructor dependency or factory callback) without putting provider objects into `TargetProfile` serialization. Provider objects are runtime dependencies; profile JSON stores only `template_resource_id` and provider ID metadata.

Verify focused engine, template, and provider tests plus import smoke.

Commit: `feat: expose runtime template provider composition`

### Task 4 — P4 checkpoint and compatibility audit

Files:

- `docs/PERCEPTION_ENGINE_CHECKPOINT.md`
- `ITERATION_LOG.md`
- `CODEBASE.md`
- `docs/plans/2026-09-03-perception-engine-implementation-plan.md`

Run:

```powershell
D:\ACloud\.venv\Scripts\python.exe -m unittest tests.test_perception_providers tests.test_perception_template_adapter tests.test_perception_algorithms tests.test_perception_engine tests.test_perception_pipeline tests.test_perception_stages -v
D:\ACloud\.venv\Scripts\python.exe -m compileall -q core/perception
git diff --check
```

Classify failures before marking the checkpoint. Confirm no `virtual_gamepad/`, Portal/Loot, navigation, input, or GUI file is staged.

Commit: `feat: add reusable template algorithm adapters`

## Non-goals

- No OCR, feature, shape, motion, or ML implementation in this slice.
- No GUI workbench wiring; that belongs to P6.
- No changes to old minimap/Portal/Loot behavior.
- No mandatory template resource backend; P3 only provides the contract and P4 uses explicit runtime injection.
