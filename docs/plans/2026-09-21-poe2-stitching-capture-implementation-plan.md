# PoE2 启动局部地图拼接采集实施计划

## Goal

在 PoE2 数据采集测试窗口中复用绘图底层，得到可保存、可审计的连续局部拼接地图和相对人物轨迹。

## Architecture Overview

新增 PoE2 stitching session 作为 `CaptureEvidence` 与通用 `MapStitcher` 之间的业务适配层。窗口只调用会话公开方法并渲染不可变 snapshot；原绘图模式和正式定位 runtime 保持不变。

## Tech Stack

Python 3.11、PySide6、OpenCV、NumPy、pytest；现有 `auto_modules.core.mapping` 和 PoE2 capture evidence 契约。

### Task 1: 定义拼图会话与快照契约

Files:

- `tests/poe2_live_terrain/test_stitching_session.py`
- `src/auto_modules/features/poe2/live_terrain/stitching_session.py`

先写失败测试，覆盖初始状态、start/pause/reset、暂停时不消费帧。实现不可变 `Poe2StitchingSnapshot` 与 `Poe2StitchingSession`：

```python
@dataclass(frozen=True)
class Poe2StitchingSnapshot:
    state: str
    map_image: np.ndarray | None
    current_position: tuple[int, int] | None
    trajectory: tuple[tuple[int, int], ...]
    statistics: Mapping[str, float | int]

class Poe2StitchingSession:
    def start(self) -> Poe2StitchingSnapshot: ...
    def pause(self) -> Poe2StitchingSnapshot: ...
    def reset(self) -> Poe2StitchingSnapshot: ...
    def consume(self, evidence: CaptureEvidence) -> Poe2StitchingSnapshot: ...
```

Verify:

```powershell
& D:/ACloud/.venv/Scripts/python.exe -m pytest tests/poe2_live_terrain/test_stitching_session.py -q
# Before implementation: collection/import failure
# After implementation: all tests pass
```

### Task 2: 适配 capture evidence 到通用绘图层

Files:

- `tests/poe2_live_terrain/test_stitching_session.py`
- `src/auto_modules/features/poe2/live_terrain/stitching_session.py`

先增加合成平移帧测试，再实现 `consume()`：校验 feature 为二维非空数组，构建零 fog mask，将 feature 同时作为稳定 match/save 层，通过公开 `MapStitcher.add_evidence()` 消费，并只在已接受帧后记录位置。

```python
evidence = MapFrameEvidence(
    image=capture.raw,
    match_mask=capture.feature,
    save_mask=capture.feature,
    fog_mask=np.zeros_like(capture.feature),
    raw_gray=capture.processed,
    player_position=rounded_player_position,
)
accepted = self._stitcher.add_evidence(evidence)
```

Verify: 同一帧稳定、平移帧轨迹连续、暂停帧不改变统计。

### Task 3: 增加实验归档契约

Files:

- `tests/poe2_live_terrain/test_stitching_session.py`
- `src/auto_modules/features/poe2/live_terrain/stitching_session.py`

先写保存内容和失败清理测试，再新增显式 archive：

```python
class Poe2StitchingArchive:
    def save(
        self,
        snapshot: Poe2StitchingSnapshot,
        evidence: CaptureEvidence,
    ) -> Path: ...
```

保存 `stitched_map.png`、轨迹 overlay、`raw.png`、`processed.png`、`feature.png`、`wall_mask.png`、`fog_mask.png`、可选同实例 `terrain.png` 和 `session.json`；使用继承父目录 ACL 的普通隐藏目录写完后原子发布。

Verify: manifest 包含轨迹、统计、monitor config 和图片尺寸，缺少拼图结果时 fail closed。

### Task 4: 扩展截图监控窗口

Files:

- `tests/test_poe2_capture_monitor_window.py`
- `src/auto_modules/ui/modes/poe2_live_terrain/capture_monitor_window.py`

先写按钮/状态/刷新测试。窗口构造函数新增 session 和 archive 依赖，布局增加绘图工具栏、主地图和统计标签。`refresh_frame()` 对同一 evidence 只调用一次 session：

```python
self._set_frame(evidence)
if self._stitching.state == "running":
    self._render_stitching(self._stitching.consume(evidence))
```

Verify: 开始、暂停、重置、保存按钮状态正确；关闭窗口停止定时器；原历史样本浏览仍通过。

### Task 5: 在组合根注入独立会话与归档

Files:

- `tests/test_poe2_composition.py`
- `src/auto_modules/ui/modes/poe2/composition.py`
- `src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`

先写 composition 测试，再从 writable root 创建实验 archive；每次打开窗口创建独立会话，避免跨窗口共享状态。输出目录：

```text
data/poe2_live_terrain_test/stitching_sessions/<timestamp-profile>/
```

Verify: 原 `capture_sample_archive` 与新增 stitching archive 相互独立，窗口单例生命周期不变。

### Task 6: 聚焦回归和代码库同步

Files:

- `docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md`
- `CODEBASE.md`
- `ITERATION_LOG.md`

Verify:

```powershell
& D:/ACloud/.venv/Scripts/python.exe -m pytest tests/poe2_live_terrain tests/test_poe2_capture_monitor_window.py tests/test_poe2_capture_test_page.py tests/test_poe2_composition.py tests/test_architecture_boundaries.py -q
& D:/ACloud/.venv/Scripts/python.exe -m compileall -q src tools tests
git diff --check
& D:/ACloud/.venv/Scripts/python.exe -m pytest -q
```

Expected: focused tests and compile pass；full suite only retains documented pre-existing PathFinder failures if unchanged.
