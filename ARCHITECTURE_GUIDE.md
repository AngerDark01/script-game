# Architecture Guide

本文定义 Auto Modules 当前有效的分层边界和扩展规则。`CODEBASE.md` 描述代码当前实现，`ARCHITECTURE_ITERATION_LOG.md` 保留历史审计过程，`docs/architecture/` 保存迁移前后的专题材料。

## 核心哲学

每一层都应在自己的稳定职责内达到最大“实用通用性”。先建设可复用能力，再在更高层组合业务；不能因为一个业务需要，就把它的术语和策略塞进共享底层。

“实用”意味着：只有语义稳定且已有真实或明确近期复用场景的能力才下沉。不要为假想需求建立框架。

```text
基础能力
识别、坐标、地图、路径、状态机、调度、控制器状态、协议契约
        ↓
通用领域运行时
定位、导航任务、事件生命周期、状态合并、恢复
        ↓
组合与适配器
应用用例、GUI、OCR 后端、Windows、Host、设备、配置、网络
        ↓
业务功能
传送门、跟随策略、技能流程、游戏规则
```

例如传送门功能只定义目标证据、接近/交互策略和完成条件；识别、定位、路径规划、移动、控制器输出和结果观察都由下层通用模块提供。

## 当前目录职责

| 路径 | 稳定职责 | 可以依赖 |
| --- | --- | --- |
| `src/auto_modules/core/` | 纯算法、领域契约、状态机、任务和意图 | 标准库、算法依赖、其他 core 模块 |
| `src/auto_modules/application/` | 跨能力用例、应用级生命周期和业务编排 | core、显式注入的适配器接口 |
| `src/auto_modules/adapters/` | Windows、输入、OCR、Host、文件和设备副作用 | core，必要时 application contract |
| `src/auto_modules/features/<game>/` | 游戏专用业务定义、策略、训练模型组合和业务诊断 | core、application、adapters；不被 core 反向依赖 |
| `src/auto_modules/ui/` | PySide6 展示、交互和页面协调 | core、application、adapters |
| `src/auto_modules/bootstrap/` | 权限、单实例、日志和进程装配 | 所有运行时层，但不承载业务算法 |
| `services/` | 可独立构建和测试的进程/协议服务 | 自身契约和明确的服务依赖 |
| `resources/` | 随程序发布的不可变资源；游戏资产位于 `games/<game>/` | 无运行时写入 |
| `data/` | 用户或运行时可写数据 | 由路径 API 定位 |
| `tools/` | 显式执行的探针、诊断和维护工具 | 可组合生产模块，但不被生产模块反向依赖 |
| `packaging/` | 离线 payload、安装器和发布验证 | 稳定入口、资源与服务产物 |

## 强制边界

- `core` 不得导入 `application`、`adapters`、`ui` 或 `bootstrap`。
- 共享模块不得按具体事件、游戏物体、技能、角色或页面名称分支。
- 通用规划和事件模块只产出 observation、task、intent、action 或 command；真实输入和网络副作用由执行适配器承担。
- 业务功能通过显式接口、typed data、配置、策略、hook 或 adapter 组合底层能力，不复制识别、定位、规划、调度、控制器或传输逻辑。
- 可变状态必须由 controller、device、source 或 feature instance 明确持有；不同实例不能通过全局快捷状态互相覆盖。
- 新功能不应要求修改多个无关业务。优先新增定义、策略、配置或适配器；只有真正通用的窄能力才允许修改共享层。
- 生产 Python 导入统一使用 `auto_modules.*`，不创建旧顶层包兼容壳。

## 游戏业务域

游戏专用实现必须在 `features/<game>/` 内形成闭合业务域；UI 只放对应的
`ui/modes/<game>/`，实验和探针只放 `tools/experiments/<game>/` 或
`tools/probes/`。这些目录可以组合通用能力，但通用层不能导入它们。

当前正式业务域：

```text
features/torchlight/
  portal/       # Torchlight 传送门识别、策略、完成条件和事件定义
  loot/         # Torchlight 掉落识别、拾取策略和事件定义
  follow/       # Torchlight 自动跟随配置、规划、控制工作进程和诊断
  skills/       # Torchlight 技能/事件链业务 facade
features/poe2/live_terrain/
  # PoE2 地形采集后的业务参考、校准、人物策略和定位组合
```

`core/events/automation/action_sequence.py` 只提供有界、声明式动作序列
运行时；Torchlight 的 `skills` facade 负责业务命名。旧的
`core.events.follow_chain` 已删除。

`MainWindow` 通过 `ui/modes/torchlight/navigation.py` 将 Torchlight 事件注册表
工厂、窗口查找器和 Loot 调试 overlay provider 注入通用导航页；通用导航和事件
管理对话框不识别游戏名、Portal/Loot 类型或业务参数。业务 definition 通过通用
schema 的 `compact`/`summary` 元数据决定参数展示。PoE2 的正式组合位于
`features/poe2/live_terrain`；`tools/experiments/poe2_live_terrain` 仅作为
兼容导出和实验入口，不承载生产实现。

资源遵循同一边界：Torchlight 的 Portal/Loot 模板与 detector 参数位于
`resources/games/torchlight/`；通用 OCR 等可跨业务复用的模型继续位于
`resources/assets/`。业务资产不能因为被 detector 读取就放进通用资源目录。

## 运行时装配

```text
main.py
  -> auto_modules.bootstrap.main
       -> 进程输出 / DPI / UAC / 单实例
       -> auto_modules.ui.main_window.MainWindow
            -> UI composition
            -> application runtimes
            -> adapters
            -> core capabilities
```

虚拟手柄和 LAN 链路：

```text
业务 intent/action
  -> adapters.virtual_gamepad
  -> Named Pipe
  -> services/virtual_gamepad Host
       -> 本机 ViGEm 输出
       -> services/lan_input_sync（可选、显式启用）
```

事件工作台：

```text
EventWorkbenchPage
  -> application.event_workbench.EventWorkbenchService
       -> core.events definitions/routes/session
       -> adapters.windows.hotkeys
       -> adapters.host.event_bridge
```

通信运行时：

```text
Follow / Event / future Map feature
        -> application.communication.CommunicationManager
             -> one PeerSession per peer
                  -> capability leases + MessageDispatcher
                       -> adapters.host.HostCommunicationAdapter
                            -> one VirtualGamepadClient / Host pipe
                                 -> C# LanSyncService TLS + UDP session
```

通信的配对、活动 session、逻辑能力和业务订阅是四个不同生命周期。业务只能申请
`input.*`、`position.*`、`event.*`、`catalog.*` 或预留的 `map.*` capability，不能
自行创建 Host client、LAN session 或消费 `sync.share.drain`。普通断线和进程重启由信任
记录与恢复偏好驱动自动重连；用户手动断开、停止、忘记设备或急停会清除恢复资格。
同一 peer 的输入、位置、事件和未来地图能力复用一个物理 session；输入接收仍保持
Controller 独占和 watchdog/急停归零语义。

地图同步本轮只定义 `map.publish`、`map.subscribe` 和 versioned-resource Envelope
字段，不实现地图存储、chunk 合并或地图 UI。未来地图业务应作为 feature 插件接入，
不修改位置、事件和输入的物理连接层。

## 路径与发布契约

`src/auto_modules/paths.py` 是仓库和安装态的统一路径入口：

- `repository_root()`：源码仓库或安装 payload 的 `app` 根目录。
- `resource_root()`：默认 `<root>/resources`，支持 `AUTO_MODULES_RESOURCE_DIR`。
- `data_root()`：默认 `<root>/data`，支持 `AUTO_MODULES_DATA_DIR`。

安装 payload 保持 `app/main.py`、`app/src/auto_modules/` 和 `app/resources/`。安装器把默认配置、控制器 profile 和地图种子放在 `defaults/`，首次启动时只补缺失内容，不覆盖用户数据。

## 验证规则

1. 在最低可行层测试纯模块和算法。
2. 在 adapter 层验证契约、超时、错误和副作用隔离。
3. 在 application/UI 层验证组合关系，不用固定页面总数替代行为断言。
4. 变更虚拟手柄、LAN、OCR 或桌面控制前先做调用链和影响面分析。
5. 真实输入、真实 Host/LAN 同步和游戏内验证保持显式 opt-in；普通回归使用 fake、loopback 或 offscreen 环境。

## PoE2 Live Terrain Preview

PoE2 实时地形是一个业务适配器，不是离线地图系统的第二个实现：

```text
external live_preview.py
  -> adapters/poe2_live_terrain
     command/session validation + native_grid conversion + memory store
  -> ui/modes/poe2_live_terrain
     initialize/capture/reset controls + read-only rendering
  -> MainWindow mode registration
```

- `src/auto_modules/adapters/poe2_live_terrain/` 是唯一的运行时转换和会话实现；
  `tools/experiments/poe2_live_terrain/` 只保留源码试验导出，不复制业务逻辑。
- 外部 `native_grid.npz` 保持原生 `yx` 方向；读取使用 `allow_pickle=False`，
  数组进入 `TerrainSnapshot` 后复制并设为只读。
- `presenter.py` 不改变快照数组：以 `cell_state == 1` 的已知可行走区域生成
  深灰底面，并从其显式黑色边界推导白色轮廓；阻挡矩形外的分类单元不会被
  直接整块画成白色。
- 页面不依赖 `AppContext.stitcher`、`NavigationCore` 或 `PathFinder`，不写
  `data/maps`，不启动 Host/LAN，不发送真实输入。当前主窗口通过显式的
  `TerrainDebugArchive` 将最新转换快照临时保存到 `data/poe2_live_terrain_test/`
  供实机核对；页面仍只从内存快照渲染。
- 当前服务生命周期为 `init -> capture -> reset/invalidate`；捕获失败清除旧快照，
  过期会话、checkpoint 历史输出和错误工具标记都必须拒绝。采集、校验、转换、
  归档和 UI 展示步骤写入 `data/logs/poe2_live_terrain.log`。
- 自动跟随只能在未来作为新的上层业务组合消费快照，不能反向污染采集适配器或通用地图模块。

## 参考

- [README.md](README.md)
- [CODEBASE.md](CODEBASE.md)
- [ITERATION_LOG.md](ITERATION_LOG.md)
- [docs/plans/2026-09-18-repository-layout-design.md](docs/plans/2026-09-18-repository-layout-design.md)
- [docs/plans/2026-09-18-repository-layout-implementation.md](docs/plans/2026-09-18-repository-layout-implementation.md)
- [docs/architecture/zh-CN/ARCHITECTURE_GUIDE.md](docs/architecture/zh-CN/ARCHITECTURE_GUIDE.md)
