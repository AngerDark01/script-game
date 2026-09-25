# PoE2 正式实时视觉定位实施计划

## Goal

将已验证的 PoE2 hybrid 定位链接入正式实时地形页面，在完整地图上持续显示人物位置和轨迹，并在视觉丢失时以一次内存锚点自动恢复。

## Architecture Overview

保留 `HybridLocalizationController` 与 `Poe2HybridLocalizationSession` 作为 PoE2 定位域实现，复用导航模式的“全局定位 -> 局部跟踪 -> 丢失恢复”状态语义。新增一个不依赖 Qt 的产品运行时适配器，把 snapshot/config 生命周期、hybrid experiment 和页面展示状态连接起来。正式 `Poe2LiveTerrainPage.monitor_timer` 是唯一产品 tick 驱动者；数据采集页不再由正式页面装配活动 hybrid session。

## Tech Stack

- Python 3.11+
- PySide6 / Qt `QTimer`
- NumPy / OpenCV
- pytest
- 项目现有 `Poe2TerrainService`、hybrid localization、presenter 和 profile store

### Task 1: 固化产品运行时生命周期契约

Files:

- `tests/poe2_live_terrain/test_hybrid_product_runtime.py`
- `src/auto_modules/features/poe2/live_terrain/hybrid_product_runtime.py`

先写失败测试，使用 fake experiment/session 验证：

```python
def test_runtime_requires_snapshot_before_start():
    runtime = Poe2HybridProductRuntime(
        experiment_factory=lambda snapshot, config_provider: None,
        initial_config=object(),
    )
    with pytest.raises(RuntimeError, match="请先获取当前地图"):
        runtime.start()


def test_configure_snapshot_builds_one_experiment_and_tick_delegates():
    session = FakeSession(result=STATE)
    factory = RecordingFactory(FakeExperiment(session))
    runtime = Poe2HybridProductRuntime(factory, initial_config=CONFIG)

    runtime.configure_snapshot(SNAPSHOT)
    runtime.start()
    result = runtime.tick(now_ms=123)

    assert factory.snapshots == [SNAPSHOT]
    assert session.events == ["start", ("tick", 123)]
    assert result.position == STATE.position


def test_replacing_snapshot_stops_previous_session():
    first = FakeSession(result=STATE)
    second = FakeSession(result=STATE)
    runtime = Poe2HybridProductRuntime(
        SequencedFactory(first, second),
        initial_config=CONFIG,
    )
    runtime.configure_snapshot(SNAPSHOT)
    runtime.start()
    runtime.configure_snapshot(OTHER_SNAPSHOT)
    assert first.events[-1] == "stop"
```

Run and expect failure:

```powershell
& D:/ACloud/.venv/Scripts/python.exe -m pytest tests/poe2_live_terrain/test_hybrid_product_runtime.py -q
# Expected: collection error because hybrid_product_runtime does not exist
```

Implement the minimal runtime:

```python
class Poe2HybridProductRuntime:
    def __init__(self, experiment_factory, *, initial_config, logger=None):
        self._factory = experiment_factory
        self._config = initial_config
        self._logger = logger
        self._snapshot = None
        self._experiment = None

    @property
    def experiment(self):
        return self._experiment

    def configure_monitor(self, config):
        self._config = config

    def configure_snapshot(self, snapshot):
        self.stop()
        self._snapshot = snapshot
        self._experiment = self._factory(snapshot, lambda: self._config)

    def start(self):
        if self._experiment is None:
            raise RuntimeError("请先获取当前地图")
        self._experiment.session.start()

    def stop(self):
        if self._experiment is not None:
            self._experiment.session.stop()

    def tick(self, *, now_ms=None):
        if self._experiment is None:
            raise RuntimeError("请先获取当前地图")
        return self._experiment.session.tick(now_ms=now_ms)

    def retry_recovery(self):
        if self._experiment is None:
            raise RuntimeError("当前没有可恢复的定位会话")
        self._experiment.session.retry_recovery()
```

Verify:

```powershell
& D:/ACloud/.venv/Scripts/python.exe -m pytest tests/poe2_live_terrain/test_hybrid_product_runtime.py -q
# Expected: all tests passed
```

Commit checkpoint: `feat: add poe2 hybrid product runtime`

### Task 2: 向产品运行时暴露最近视觉帧

Files:

- `tests/poe2_live_terrain/test_hybrid_localization_session.py`
- `src/auto_modules/features/poe2/live_terrain/experimental/hybrid_localization/session.py`
- `tests/poe2_live_terrain/test_hybrid_product_runtime.py`
- `src/auto_modules/features/poe2/live_terrain/hybrid_product_runtime.py`

先增加失败测试：

```python
def test_tick_keeps_latest_raw_frame_and_evidence():
    state = session.tick(now_ms=123)
    assert session.last_raw_frame is raw_frame
    assert session.last_evidence is evidence
    assert session.last_frame is not None


def test_product_state_contains_visual_previews():
    state = runtime.tick(now_ms=123)
    assert state.raw_frame is RAW
    assert state.processed_frame is PROCESSED
    assert state.match_mask is MASK
    assert state.reason == HYBRID_STATE.reason
```

Run and expect attribute failures:

```powershell
& D:/ACloud/.venv/Scripts/python.exe -m pytest tests/poe2_live_terrain/test_hybrid_localization_session.py tests/poe2_live_terrain/test_hybrid_product_runtime.py -q
# Expected: failures for missing last_raw_frame/product view state
```

Add session-owned read-only latest values, resetting them on `reset()` and setting them only after successful capture/evidence construction:

```python
self.last_raw_frame = None
self.last_evidence = None
self.last_frame = None

raw = self.frame_source.capture(config)
evidence = self.evidence_builder.build(raw, config)
frame = HybridFrame.from_evidence(...)
self.last_raw_frame = raw
self.last_evidence = evidence
self.last_frame = frame
```

Return a product state adapter containing the hybrid state plus:

```python
@dataclass(frozen=True)
class Poe2HybridProductState:
    mode: Any
    position: tuple[float, float] | None
    latest_confirmed_position: tuple[float, float] | None
    trajectory: tuple[tuple[float, float], ...]
    source: str
    confidence: float
    reason: str
    recovery_revision: int
    diagnostics: Mapping[str, Any]
    raw_frame: Any = None
    processed_frame: Any = None
    match_mask: Any = None
    frame_elapsed_ms: float = 0.0
```

`processed_frame` 从 evidence 的处理帧取得，`match_mask` 优先取 `wall_mask`，没有时取 `feature`。不要把 Qt 类型放入该状态。

Verify:

```powershell
& D:/ACloud/.venv/Scripts/python.exe -m pytest tests/poe2_live_terrain/test_hybrid_localization_session.py tests/poe2_live_terrain/test_hybrid_product_runtime.py -q
# Expected: all tests passed
```

Commit checkpoint: `feat: expose hybrid localization visual state`

### Task 3: 让 composition 将 hybrid 产品运行时注入正式页面

Files:

- `tests/test_poe2_composition.py`
- `src/auto_modules/ui/modes/poe2/composition.py`
- `src/auto_modules/features/poe2/live_terrain/__init__.py`

先写失败测试：

```python
def test_composition_uses_hybrid_product_runtime_for_formal_page(tmp_path):
    composition = build_poe2_live_terrain_composition(
        screen_capture=FakeScreenCapture(),
        recognizer=object(),
        writable_root=tmp_path,
    )
    assert isinstance(composition.runtime, Poe2HybridProductRuntime)
    assert composition.runtime.experiment is None
```

Run and expect the old runtime assertion to fail:

```powershell
& D:/ACloud/.venv/Scripts/python.exe -m pytest tests/test_poe2_composition.py -q
# Expected: formal composition still provides Poe2LocalizationRuntime
```

After defining `build_hybrid_localization`, construct:

```python
runtime = Poe2HybridProductRuntime(
    build_hybrid_localization,
    initial_config=profile_store.active() or config_store.load(),
    logger=get_terrain_logger(),
)
```

Remove the old formal `Poe2LocalizationRuntime` construction from this composition only. Do not delete the legacy runtime module because focused tests and other callers may still use it.

Verify:

```powershell
& D:/ACloud/.venv/Scripts/python.exe -m pytest tests/test_poe2_composition.py tests/poe2_live_terrain/test_localization_runtime.py -q
# Expected: all tests passed
```

Commit checkpoint: `feat: compose hybrid runtime for poe2 live terrain`

### Task 4: 对齐正式页面的 hybrid 状态与自动恢复展示

Files:

- `tests/test_poe2_live_terrain_monitoring.py`
- `tests/test_poe2_live_terrain_presenter_position.py`
- `src/auto_modules/ui/modes/poe2_live_terrain/page.py`

先增加页面行为测试：

```python
def test_formal_page_renders_hybrid_reason_revision_and_read_count(qtbot):
    page = Poe2LiveTerrainPage(service=service, runtime=runtime)
    page._terrain_display = DISPLAY
    page.handle_runtime_state(HYBRID_PRODUCT_STATE)
    text = page.localization_status.text()
    assert "visual_local" in text
    assert "恢复版本：2" in text
    assert "内存读取：1" in text
    assert overlay_was_rendered(page.map_widget)


def test_recovery_required_does_not_stop_monitor_timer(qtbot):
    page.start_monitoring()
    page.handle_runtime_state(RECOVERY_REQUIRED_STATE)
    assert page.monitor_timer.isActive()
    assert "需要重新定位" in page.localization_status.text()
```

Run and expect status assertions to fail:

```powershell
& D:/ACloud/.venv/Scripts/python.exe -m pytest tests/test_poe2_live_terrain_monitoring.py tests/test_poe2_live_terrain_presenter_position.py -q
# Expected: failures for missing hybrid status fields
```

Update `handle_runtime_state()` to use both legacy and hybrid field names:

```python
reason = str(
    getattr(state, "reason", "")
    or getattr(state, "failure_reason", "")
    or ""
)
diagnostics = dict(
    getattr(state, "diagnostics", None)
    or getattr(state, "recognition_diagnostics", None)
    or {}
)
mode = getattr(getattr(state, "mode", ""), "value", getattr(state, "mode", ""))
revision = int(getattr(state, "recovery_revision", 0))
read_count = int(getattr(state, "memory_read_count", 0))
```

状态文本必须区分“本帧位置”和“最后可信位置”。`RECOVERY_REQUIRED` 不追加轨迹、不伪造新位置，也不停止 timer；只有用户停止监控或运行时抛出不可恢复异常才停止。

Verify:

```powershell
& D:/ACloud/.venv/Scripts/python.exe -m pytest tests/test_poe2_live_terrain_monitoring.py tests/test_poe2_live_terrain_presenter_position.py tests/test_poe2_live_terrain_page.py -q
# Expected: all tests passed
```

Commit checkpoint: `feat: render hybrid localization on formal poe2 page`

### Task 5: 保证正式页面只有一个活动定位 owner

Files:

- `tests/test_poe2_live_terrain_page.py`
- `tests/test_poe2_capture_test_page.py`
- `src/auto_modules/ui/modes/poe2_live_terrain/page.py`

先写失败测试：

```python
def test_formal_page_does_not_inject_live_hybrid_factory_into_capture_tab(qtbot):
    page = Poe2LiveTerrainPage(
        service=service,
        runtime=runtime,
        hybrid_localization_factory=hybrid_factory,
        capture_test_service=capture_service,
    )
    assert page.capture_test_page.hybrid_localization_factory is None
    assert not page.capture_test_page.hybrid_timer.isActive()
```

Run and expect the factory ownership assertion to fail:

```powershell
& D:/ACloud/.venv/Scripts/python.exe -m pytest tests/test_poe2_live_terrain_page.py tests/test_poe2_capture_test_page.py -q
# Expected: formal page currently passes the factory to capture test page
```

Keep the test page implementation available for standalone diagnostics, but construct the embedded capture tab with:

```python
hybrid_localization_factory=None
```

The formal page runtime remains the only session driven by the product window. Existing screenshot, sample, stitching, and archive functions stay unchanged.

Verify:

```powershell
& D:/ACloud/.venv/Scripts/python.exe -m pytest tests/test_poe2_live_terrain_page.py tests/test_poe2_capture_test_page.py -q
# Expected: assertions pass; note any existing Qt GC process-exit issue separately
```

Commit checkpoint: `refactor: keep poe2 capture tab diagnostic only`

### Task 6: 验证自动单次恢复调用链

Files:

- `tests/poe2_live_terrain/test_hybrid_localization_integration.py`
- `docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md`
- `CODEBASE.md`
- `ITERATION_LOG.md`

增加端到端 fake 测试：

```python
def test_product_runtime_reads_anchor_on_first_frame_and_once_after_visual_loss():
    runtime.configure_snapshot(SNAPSHOT)
    runtime.start()

    first = runtime.tick()
    local = runtime.tick()
    lost = runtime.tick()
    recovered = runtime.tick()

    assert first.source == "anchored_absolute"
    assert local.source == "visual_local"
    assert lost.mode.value == "recovery_pending"
    assert recovered.source == "anchored_absolute"
    assert anchor_provider.read_count == 2


def test_failed_recovery_does_not_poll_memory_every_tick():
    drive_to_failed_recovery(runtime)
    reads = anchor_provider.read_count
    for _ in range(5):
        state = runtime.tick()
        assert state.mode.value == "recovery_required"
    assert anchor_provider.read_count == reads
```

Run the focused suite:

```powershell
& D:/ACloud/.venv/Scripts/python.exe -m pytest tests/poe2_live_terrain/test_hybrid_product_runtime.py tests/poe2_live_terrain/test_hybrid_localization_controller.py tests/poe2_live_terrain/test_hybrid_localization_session.py tests/poe2_live_terrain/test_hybrid_localization_integration.py tests/test_poe2_composition.py tests/test_poe2_live_terrain_monitoring.py tests/test_poe2_live_terrain_page.py tests/test_poe2_live_terrain_presenter_position.py -q
# Expected: all assertions passed
```

Run static and diff checks:

```powershell
& D:/ACloud/.venv/Scripts/python.exe -m compileall -q src/auto_modules
git diff --check
# Expected: both exit 0
```

Update the current-state and architecture documents with the final call chain, state ownership, test results, known Qt GC limitation, and any remaining real-device verification.

Commit checkpoint: `test: verify poe2 visual tracking recovery flow`
