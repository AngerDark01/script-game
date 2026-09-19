# PoE2 实时地形预览设计

## 实施状态（2026-09-19）

第一阶段已实现。经过契约验证后，稳定的运行时实现落在
`src/auto_modules/adapters/poe2_live_terrain/`，而
`tools/experiments/poe2_live_terrain/` 仅保留兼容导出，避免实验目录与正式
运行时形成两套逻辑。本文的“实验后端”表述指验证边界和外部采集器，不表示
正式页面仍直接依赖 `tools/experiments`。

## 目标

在不改变离线绘图/导航地图生命周期的前提下，为 PoE2 增加一个独立业务页面：用户启动游戏后手动初始化，进入异界后手动抓取当前实例地形，程序将外部采集器产物转换为内存快照并展示。

## 范围

第一阶段只包含初始化、手动抓取、校验、转换、内存缓存和只读展示。暂不包含自动跟随、玩家定位、路径规划、Xbox 输入、动态障碍、地图持久化或真实网络同步。

## 分层设计

```text
PoE2 采集器（外部项目）
        -> tools/experiments/poe2_live_terrain
           会话、采集命令、NPZ 校验与转换、内存服务
        -> src/auto_modules/ui/modes/poe2_live_terrain
           页面、状态和只读地图展示
        -> src/auto_modules/ui/main_window.py
           仅挂载新页面
```

- 外部采集器仍属于 `D:\ACloud\poe2-map-research`，主项目通过显式路径/命令适配，不复制采集实现。
- 实验后端先放在 `tools/experiments/poe2_live_terrain/`，便于验证后再决定哪些契约下沉到正式 `core` 或 `application`。
- 页面只依赖注入的服务接口，不直接启动进程、不读取 NPZ、不访问正式地图目录。
- 读取成功的数组必须复制到不可变/只读内存快照；不写 `data/maps`、`map_data.npz` 或用户配置。
- 保留 native `yx` 数组方向；`raw_cells`、`cell_state`、`known_mask`、`wall_layer`、`explored_map` 的语义遵循外部 `DATA-CONTRACT.md`。
- 不伪造玩家坐标；动态障碍与实时定位留给后续业务。

## 会话状态

```text
NEW -> INITIALIZED -> READY_TO_CAPTURE -> CAPTURED
  \-> ERROR
INITIALIZED/READY_TO_CAPTURE/CAPTURED -> INVALIDATED
```

初始化记录当前 PoE2 进程会话；抓取前必须存在有效初始化。进程、客户端或实例变化时失败关闭并清除旧快照；失败抓取不能继续显示旧地图。

## 外部数据边界

采集器使用 `init` 和 `capture` 两个命令。适配器只接受成功命令产生的 `output/latest.json`，并要求：`tool == manual-live-terrain-capture`、没有 checkpoint 字段、manifest/NPZ 存在、NPZ 使用 `allow_pickle=False` 可加载且数组形状一致。历史输出或失败命令不得被当作当前结果。

## UI 设计

- 新增“PoE2 地形”页面和模式按钮。
- 页面提供“初始化”“获取当前地图”“清空当前地图”。
- 未初始化时禁用抓取；抓取期间禁用重复操作；错误显示原因。
- 成功后展示 area、instance、尺寸、抓取时间、完整性和地形图。
- 复用现有 `ScalableMapWidget` 与主题，不复用 `MappingWidget` 的 `MapStitcher`、定时器、保存地图或 `AppContext` 状态。
- 页面关闭或主窗口关闭只释放本页缓存，不启动 Host、LAN 或真实输入。

## 验收标准

1. 合成 NPZ 能转换为正确的 `yx` 内存快照，dtype、尺寸和分类语义明确。
2. 未运行 PoE2、未初始化、过期会话、错误工具标记、checkpoint 历史输出和校验失败均明确拒绝。
3. 成功抓取只更新内存快照，不产生 `data/maps` 文件。
4. UI 可通过 fake service 测试初始化、抓取、错误和清空，不需要真实游戏。
5. MainWindow 保持现有页面索引和关闭安全行为，新页面独立挂载。
