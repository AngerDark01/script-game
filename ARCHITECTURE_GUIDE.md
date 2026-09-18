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
| `src/auto_modules/ui/` | PySide6 展示、交互和页面协调 | core、application、adapters |
| `src/auto_modules/bootstrap/` | 权限、单实例、日志和进程装配 | 所有运行时层，但不承载业务算法 |
| `services/` | 可独立构建和测试的进程/协议服务 | 自身契约和明确的服务依赖 |
| `resources/` | 随程序发布的不可变资源 | 无运行时写入 |
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

## 参考

- [README.md](README.md)
- [CODEBASE.md](CODEBASE.md)
- [ITERATION_LOG.md](ITERATION_LOG.md)
- [docs/plans/2026-09-18-repository-layout-design.md](docs/plans/2026-09-18-repository-layout-design.md)
- [docs/plans/2026-09-18-repository-layout-implementation.md](docs/plans/2026-09-18-repository-layout-implementation.md)
- [docs/architecture/zh-CN/ARCHITECTURE_GUIDE.md](docs/architecture/zh-CN/ARCHITECTURE_GUIDE.md)
