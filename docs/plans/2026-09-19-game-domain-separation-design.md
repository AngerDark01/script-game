# 游戏业务域与通用引擎分离设计

## 状态

已确认，2026-09-19。

## 目标

把 Auto Modules 拆成稳定的通用引擎、外部适配器、游戏业务域和实验/训练工具，使火炬之光的传送门、掉落、跟随和技能流程只存在于火炬之光业务域，不再污染 `core` 的通用能力。

## 核心判断

传送门、掉落和跟随不是通用业务。它们是火炬之光自动化脚本的具体业务；PoE2 是另一个平级业务域。真正通用的是实体识别契约、图像预处理、定位、路径、动作、事件生命周期和外部 provider 接口。

当前 `core/events/types/portal`、`core/events/types/loot`、`core/routing/follower_planner.py`、`core/diagnostics/follow_*` 和 `application/follow` 的语义属于火炬之光业务，需要迁移或拆分。

## 目标结构

```text
src/auto_modules/
  core/                         # 与具体游戏无关的引擎和通用领域运行时
    foundation/                 # 几何和基础值对象
    spatial/                    # 坐标空间和映射
    perception/                 # 通用实体识别契约、算法、pipeline
    localization/               # 通用定位和地图匹配
    routing/                    # 通用路径和路线进度
    navigation_tasks/            # 通用目标接近和移动任务
    actions/                    # 设备无关动作模型
    events/                     # 通用事件生命周期和自动化运行时
    runtime/                    # 通用运行状态

  adapters/                     # 可复用的外部平台/provider/device 连接
    input/
    perception/
    platform/
    windows/
    host/
    virtual_gamepad/

  application/                  # 通用应用运行时和组合入口
    runtime/
    composition/

  features/                     # 按游戏隔离的业务域
    torchlight/
      portal/
      loot/
      follow/
      skills/
      composition.py
    poe2/
      live_terrain/
      composition.py

  ui/
    modes/
      torchlight/
      poe2/

tools/
  experiments/                  # 显式执行的实验和探针，不被生产代码导入
    torchlight/
    poe2/
  training/                     # 只有稳定复用后才下沉通用训练基础设施
    common/
    torchlight/
    poe2/

resources/
  games/
    torchlight/
    poe2/

data/
  games/
    torchlight/
    poe2/
```

## 依赖方向

```text
features/<game>
  -> core contracts and capabilities
  -> injected application ports

application/composition
  -> features/<game>
  -> core
  -> adapters

ui/modes/<game>
  -> features/<game> public API
  -> application composition

core
  -X-> features
  -X-> application
  -X-> adapters
  -X-> ui

tools
  -> production packages
production packages
  -X-> tools
```

业务 feature 不直接持有真实设备副作用。需要屏幕、OCR、输入或 Host 时，通过通用契约和应用装配注入适配器。

## 通用识别边界

`core/perception` 只产出通用结果，例如 `FrameContext`、`BoundingBox`、`TargetDetection`、provider DTO 和候选结果。它不定义传送门、掉落、火炬之光或 PoE2。

`adapters/perception` 负责 RapidOCR、ONNX Runtime、模板资源读取和外部 provider。模型运行时属于适配器；模型的业务标签、阈值和后处理属于对应游戏 feature。

火炬之光传送门和掉落分别消费通用识别能力，但自身的模型、模板、候选过滤、事件策略和完成条件留在 `features/torchlight`。

## 训练和实验边界

当前已有的掉落/图标数据集评估脚本是火炬之光专用实验，先归入 `tools/experiments/torchlight`。只有当 PoE2 或其他业务重复使用数据集读取、拆分、指标和报告逻辑时，才提取到 `tools/training/common`，避免创建未验证的通用框架。

模型和模板按游戏归属放在 `resources/games/<game>`，运行时可写结果按游戏归属放在 `data/games/<game>`。

## 迁移约束

1. 保留 `pre-reorg/2026-09-18` 作为已验证回退点。
2. 当前未提交的 PoE2 修改不得被覆盖或回滚。
3. 不创建旧顶层 `core`、`gui`、`workflows` 等兼容包。
4. 每迁移一个业务域，先更新导入，再运行该域的聚焦测试。
5. 真实输入、Host 和 LAN 同步保持显式 opt-in。
6. 不为尚未证明复用的训练流程提前建立复杂抽象。

## 验收标准

- `core` 不包含 `portal`、`loot`、`torchlight` 或 `poe2` 业务术语。
- 火炬之光的 portal、loot、follow、skills 由 `features/torchlight` 统一拥有。
- PoE2 与火炬之光互不导入对方。
- UI 不从 `core.events.types.portal` 或 `core.events.types.loot` 深层路径注册业务。
- `tools` 不被生产包反向导入。
- 通用 perception 可以在没有游戏业务模块时单独测试。
- 现有 Python 回归和新增边界测试通过；已知 Pathfinder 问题和环境依赖问题单独记录。
