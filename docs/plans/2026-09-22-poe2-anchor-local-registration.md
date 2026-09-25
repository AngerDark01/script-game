# PoE2 内存锚点局部注册实验实施计划

## Goal

在 PoE2 实验代码中，把同步样本里的内存人物坐标作为锚点，只搜索附近 terrain 小块，恢复首帧小地图的旋转、镜像、比例和平移，并输出可复核的候选报告与叠图。

## Architecture Overview

- 新实现位于 `tools/debug/`，只依赖现有 PoE2 样本契约和 `poe2_live_terrain_localization_probe.py` 的 Chamfer 搜索能力。
- 输入必须同时具有 `terrain.status=available`、`player_position.status=available`，且两个实例 ID 一致。
- 第一阶段以人物 native-grid 坐标为中心裁剪局部 terrain，并清除可配置的顶部文字带和人物中心区域。
- 第二阶段先做有限离散粗搜，再只围绕锚点附近的最佳候选做角度/比例细搜。
- 输出区分 `anchored_candidate`、`ambiguous` 和 `rejected`；单帧不会被伪装成跨帧 confirmed。
- 本阶段不修改 `src/auto_modules/core`、正式 PoE runtime、第一页绘图模式或输入/网络链路。

## Tech Stack

- Python 3.11、OpenCV、NumPy、pytest。
- 复用 `ProbeConfig`、`search_candidates`、`terrain_edges`、`terrain_walkable_mask` 和 `_candidate_overlay`。

### Task 1: 样本和锚点契约

Files:

- `tools/debug/poe2_anchor_local_registration_probe.py`
- `tests/poe2_live_terrain/test_anchor_local_registration_probe.py`

先写测试：同实例样本能够读取锚点；terrain/人物实例不一致时抛出 `ValueError`。

核心接口：

```python
@dataclass(frozen=True)
class AnchorLocalProbeInput:
    sample_root: Path
    manifest: Mapping[str, Any]
    terrain: np.ndarray
    feature: np.ndarray
    local_player: tuple[float, float]
    anchor_grid: tuple[float, float]

def load_anchor_probe_input(sample_directory: str | Path) -> AnchorLocalProbeInput:
    ...
```

Verify:

```powershell
& D:/ACloud/.venv/Scripts/python.exe -m pytest -q tests/poe2_live_terrain/test_anchor_local_registration_probe.py
# Expected: contract tests pass
```

### Task 2: 局部裁剪和实验噪声清理

Files:

- `tools/debug/poe2_anchor_local_registration_probe.py`
- `tests/poe2_live_terrain/test_anchor_local_registration_probe.py`

增加纯函数：

```python
def crop_terrain_around_anchor(
    terrain: np.ndarray,
    anchor: tuple[float, float],
    radius: int,
) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    ...

def prepare_local_feature(
    feature: np.ndarray,
    local_player: tuple[float, float],
    *,
    top_exclusion_rows: int,
    player_clear_radius: int,
) -> np.ndarray:
    ...
```

测试裁剪会在地图边界夹紧，输入数组不被修改，顶部文字带和人物中心被清除。

### Task 3: 两阶段锚点局部匹配

Files:

- `tools/debug/poe2_anchor_local_registration_probe.py`
- `tests/poe2_live_terrain/test_anchor_local_registration_probe.py`

增加：

```python
@dataclass(frozen=True)
class AnchorLocalProbeConfig:
    crop_radius: int = 180
    refine_crop_radius: int = 130
    top_exclusion_rows: int = 25
    player_clear_radius: int = 22
    max_anchor_error: float = 80.0

def match_anchor_local(
    probe_input: AnchorLocalProbeInput,
    config: AnchorLocalProbeConfig | None = None,
) -> AnchorLocalProbeResult:
    ...
```

算法步骤：

1. 以锚点裁剪粗搜 terrain。
2. 调用现有 Chamfer 搜索，过滤超出 `max_anchor_error` 的候选。
3. 按匹配分数和锚点误差选择粗候选。
4. 以粗候选角度、镜像和比例构造窄范围细搜配置。
5. 将细搜局部坐标还原为完整 terrain 坐标。
6. 根据结构覆盖、锚点误差和候选分差输出 `anchored_candidate/ambiguous/rejected`。

合成测试使用已知 `45° + 水平镜像 + 1.2 scale` 的模板，并验证人物全局位置误差。

### Task 4: CLI、诊断输出和真实样本验证

Files:

- `tools/debug/poe2_anchor_local_registration_probe.py`
- `tests/poe2_live_terrain/test_anchor_local_registration_probe.py`
- `docs/POE2_LIVE_TERRAIN_CURRENT_STATE.md`
- `CODEBASE.md`
- `ITERATION_LOG.md`

CLI：

```powershell
& D:/ACloud/.venv/Scripts/python.exe tools/debug/poe2_anchor_local_registration_probe.py `
  --sample data/poe2_live_terrain_test/samples/20260922-043532-966126-MapFlotsam-1E44BF94 `
  --output data/poe2_live_terrain_test/probe_results/anchor-local-v1
```

输出：

```text
report.json
local_terrain.png
prepared_feature.png
best_overlay.png
```

Verify:

```powershell
& D:/ACloud/.venv/Scripts/python.exe -m pytest -q `
  tests/poe2_live_terrain/test_anchor_local_registration_probe.py `
  tests/poe2_live_terrain/test_localization_probe.py
# Expected: all pass

& D:/ACloud/.venv/Scripts/python.exe -m compileall -q tools/debug/poe2_anchor_local_registration_probe.py
git diff --check
```

真实样本验收：候选保持在内存锚点附近，并生成可人工检查的连续边界叠图；即使分数不足，也必须返回明确原因，不能强制 confirmed。
