# Core Facade 逐步抽取方法论

## 目标

把 `core` 中“一个类里很多函数、一个文件几百行”的实现拆成按功能分类的 helper 模块，同时不破坏现有 GUI、任务层、工具脚本和旧 import 路径。

目标不是马上消灭类，而是让类变成稳定 facade：

```python
class SomeCore:
    def public_method(self, ...):
        return helper_pipeline(self, ...)
```

外部仍按旧方式使用：

```python
from core.some_core import SomeCore
```

## 基本原则

1. **旧入口保留**
   - 公开 class 名不改。
   - 公开方法名不改。
   - 外部直接读取的字段不改。
   - 旧私有方法如果被内部 helper 或旧测试/工具依赖，也先保留 wrapper。

2. **先分类，再抽取**
   - 输入执行放 `core/input/`。
   - 建图拼接放 `core/mapping/`。
   - 定位放 `core/localization/`。
   - 路径规划放 `core/routing/`。
   - 视觉识别放 `core/vision/`。
   - 共享契约放 `core/shared/`。

3. **小步反复抽**
   - 一次只抽一个明确功能块。
   - 每次抽完都跑 `py_compile` 和 import smoke。
   - 不在同一轮同时重写行为和移动文件。

4. **facade 写状态，helper 承接实现**
   - 低风险 helper 可以是纯函数，例如 mask scale、screen clamp。
   - 中风险 pipeline 可以接收 facade 实例并写状态，例如 `add_frame_to_stitcher(stitcher, ...)`。
   - 旧类方法保留壳子，方便外部调用不变。

5. **行为敏感流程先搬运，后重构**
   - 第一步只做代码位置移动和委托，尽量不改算法。
   - 后续再在 helper 内继续拆更小函数。
   - 不在搬运时顺手优化阈值、状态机、异常策略。

## 推荐抽取顺序

### 第一层：纯计算 helper

适合直接抽：

- 坐标换算
- mask 缩放
- 形态学处理
- IoU/相似度计算
- screen clamp
- 配置 deep merge

特点：

- 输入参数清楚。
- 返回值清楚。
- 不写 facade 状态。
- 最容易验证。

### 第二层：外部 adapter/helper

适合抽到系统包：

- Win32 driver
- pydirectinput click backend
- window diagnostics
- file IO
- map package save/load
- display rendering

特点：

- 依赖外部库或平台。
- 适合集中隔离异常和 fallback。

### 第三层：pipeline helper

适合用来压薄 facade：

- `execute_click(controller, screen_pos)`
- `add_frame_to_stitcher(stitcher, ...)`
- `localize_frame(nav_core, minimap_img, player_pos=None)`
- `update_navigation_task(controller, context)`

特点：

- 可以接收 facade 实例。
- 可以读写状态。
- 目标是把几百行类方法先搬成命名流程模块。
- 搬完之后再继续拆 pipeline 内部阶段。

## 文件命名规则

| 类型 | 命名示例 | 用途 |
| --- | --- | --- |
| 纯计算 | `frame_preparation.py`、`screen_bounds.py` | 输入输出明确，不写 facade 状态 |
| 外部适配 | `click_executor.py`、`package_io.py` | 封装 IO、平台、外部库 |
| 诊断 | `click_diagnostics.py`、`coordinate/diagnostics.py` | 收集调试信息，不改变主流程 |
| 流程编排 | `click_pipeline.py`、`frame_pipeline.py` | 承接原大方法主流程 |
| 契约 | `frame_registration.py`、`models.py` | dataclass、状态枚举、公共数据结构 |

## 每轮执行模板

1. 在 `ARCHITECTURE_ITERATION_LOG.md` 写本轮目标。
2. 读目标文件和相邻 helper。
3. 新增 helper/pipeline 文件。
4. 原类方法改成委托，旧方法名保留。
5. 更新包 `__init__.py` 导出。
6. 跑验证：

```powershell
D:\ACloud\.venv\Scripts\python.exe -m py_compile <changed files>
D:\ACloud\.venv\Scripts\python.exe -c "from old.path import OldClass; from new.package import new_helper; print('ok')"
```

7. 同步中文文档：
   - `CODEBASE.md`
   - `architecture_docs/zh-CN/core/ARCHITECTURE.md`
   - `architecture_docs/zh-CN/core/CORE_MODULARIZATION_PLAN.md`
   - `architecture_docs/zh-CN/ARCHITECTURE_ITERATION_LOG.md`

## 风险边界

不应该一次性做：

- 改公开 class 名。
- 改旧 import 路径。
- 删除旧 wrapper。
- 在搬运代码时顺手改算法阈值。
- 把多个状态机同时拆散。
- 让事件系统直接调用 `MotionController` 或输入后端。

可以做：

- 把长方法搬到 pipeline helper。
- 把纯计算搬到系统 helper。
- 让旧私有方法委托 helper。
- 让 `__init__.py` 聚合新 helper。
- 逐步降低 facade 文件行数。

## 当前已经应用的例子

- `core/motion_controller.py`
  - `core/input/motion_mapping.py`
  - `core/input/click_executor.py`
  - `core/input/click_diagnostics.py`
  - `core/input/click_pipeline.py`
  - `core/input/screen_bounds.py`

- `core/stitcher_core.py`
  - `core/mapping/package_io.py`
  - `core/mapping/performance.py`
  - `core/mapping/frame_preparation.py`
  - `core/mapping/frame_pipeline.py`
  - `core/mapping/weighted_merge.py`
  - `core/mapping/rendering.py`

- `core/localization/navigation_core/`
  - `core/localization/map_package.py`
  - `core/localization/rendering.py`
  - `core/localization/frame_registration.py`
  - `core/localization/frame_matcher.py`
  - `core/localization/visual_check.py`

## 后续方向

1. `NavigationCore.localize()` 已委托 `core/localization/localize_pipeline.py`，后续只在出现清晰复用点时继续拆内部阶段。
2. `NavigationTaskController.update_context()` 已通过 `update_pipeline.py`、`static_task_runner.py`、`event_task_runner.py` 分段；旧 `update(**kwargs)` 已删除。
3. 再回头拆 pipeline 内部阶段时，必须以状态局部性和复用方为依据。
4. class 实现已进入系统包；后续重点是清理无价值 wrapper，而不是迁移文件名。
