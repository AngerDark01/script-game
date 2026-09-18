# Auto Modules

Auto Modules 是一个面向 Windows 桌面自动化、游戏导航、事件编排、虚拟手柄和局域网设备联动的模块化工作台。项目遵循“自底向上通用化”：底层提供稳定、可复用能力，上层通过策略、配置和适配器组合具体业务。

## 启动

在仓库根目录执行：

```powershell
D:\ACloud\.venv\Scripts\python.exe main.py
```

`main.py` 只是薄启动器，实际进程初始化位于 `src/auto_modules/bootstrap/`。工作台会按现有安全策略请求所需权限；测试和离线验证不会主动发送真实输入或启动 LAN 同步。

## 分层结构

```text
auto_modules/
├── src/auto_modules/
│   ├── core/             # 通用算法、状态机、任务、意图和领域契约
│   ├── application/      # 跨核心能力的应用运行时与用例编排
│   ├── adapters/         # Windows、输入、OCR、Host、文件和设备适配器
│   ├── ui/               # PySide6 页面、对话框和展示协调
│   ├── bootstrap/        # 进程启动、权限、单实例和应用装配
│   └── paths.py          # 统一资源与可写数据路径 API
├── services/
│   ├── virtual_gamepad/  # 独立 C# Host、启动器和线协议
│   └── lan_input_sync/   # 独立 C# LAN 同步库
├── resources/            # 随程序发布的只读资源和默认模板
├── data/                 # 地图、事件、日志、诊断和本机可写数据
├── tools/                # 探针、调试和虚拟手柄开发脚本
├── packaging/            # 离线 payload 与安装器
├── docs/                 # 架构、指南、计划和历史资料
└── tests/                # Python 回归测试
```

依赖方向固定为：

```text
core -> application/adapters -> ui/bootstrap
```

这里的箭头表示上层使用左侧能力：`core` 不得导入 `application`、`adapters`、`ui` 或 `bootstrap`。真实键鼠、虚拟手柄、OCR 后端、Windows API、Host 和网络副作用只允许出现在专用适配器或独立服务中。

## Python 导入

生产代码统一使用 `auto_modules.*`：

```python
from auto_modules.core.actions import VirtualGamepadActionAdapter
from auto_modules.adapters.virtual_gamepad import connect_action_adapter
```

仓库不保留旧的 `core.*`、`gui.*`、`workflows.*` 兼容包。开发环境可安装为 editable package，测试也会通过 `pyproject.toml` 将 `src` 加入导入路径。

## 运行数据和资源

- `resources/` 是只读发布资源，可由 `AUTO_MODULES_RESOURCE_DIR` 覆盖。
- `data/` 是源码工作区默认可写目录，可由 `AUTO_MODULES_DATA_DIR` 覆盖。
- Host 目录可由 `AUTO_MODULES_HOST_DIR` 指定。
- 地图位于 `data/maps/<map-name>/`，地图包文件仍名为 `map_data.npz`。
- 控制器本机配置位于 `data/virtual_gamepad/configs/`。

所有生产路径解析都应通过 `auto_modules.paths` 或对应的上层路径适配器完成，不应再通过 `Path(__file__).parents[n]` 猜测仓库位置。

## 虚拟手柄与局域网

工作台的虚拟手柄页面连接独立 C# Host，支持两个 Xbox 360 控制器、独立配置和安全归零。自动化业务通过通用 action contract 和虚拟手柄适配器发送状态，不直接依赖 Host 协议。

局域网同步由 [services/lan_input_sync/README.md](services/lan_input_sync/README.md) 描述，虚拟手柄 Host 与开发流程见 [services/virtual_gamepad/README.md](services/virtual_gamepad/README.md)。三节点 A -> B/C 的实机事件广播和游戏内输入/技能释放已经完成实际验证；后续回归仍应区分协议回执、Host 收包和游戏实际效果三个层次。

## 开发与验证

```powershell
D:\ACloud\.venv\Scripts\python.exe -m pytest -q
```

修改虚拟手柄、LAN、OCR 或桌面输入前，先追踪调用链并运行聚焦测试。真实输入和真实网络同步必须显式选择执行，普通测试不得触发。

更完整的边界规则见 [ARCHITECTURE_GUIDE.md](ARCHITECTURE_GUIDE.md)，当前代码索引见 [CODEBASE.md](CODEBASE.md)，迁移前已验证版本由 Git 标签 `pre-reorg/2026-09-18` 保留。
