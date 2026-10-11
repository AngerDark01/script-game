# PoE2 双角色首帧定位重构方案

## Goal

把首帧定位改成“进程级通用参数一次初始化、每张地图首帧重新读取当前地图和 P1/P2、独立求局部坐标变换、以内存 anchor 做角色匹配”，同时保持现有跟随、规划、局部避障、脉冲和手柄策略不变。

## 核心边界

进程级初始化只准备跨所有异界地图通用的参数：PID、进程创建时间、ProcessReader、可执行文件身份和 build hash、模块基址、GameState 全局入口/slot RVA、版本验证后的结构偏移/指针路径/读取宽度、地址合法性规则、坐标常量、读缓冲和错误分类。

进程级初始化不读取当前地图实例，不读取当前地图数据，也不读取当前地图里的 P1/P2 身份和位置。

每次进入地图或点击首帧，都重新读取当前地图动态状态：当前 GameState/area/state、地图数据、当前 entity vector、P1/P2 metadata/身份、P1/P2 entity 和 Render 地址、P1/P2 当前内存位置。地图切换、实体重建或角色重进地图时不能沿用上一地图的角色地址。

## 目标链路

```text
process_init
  → ProcessMemoryContext
  → current_map_read
  → current_P1_P2_memory_anchors
  → local_map/frame_transform
  → projected_role_windows
  → role_candidate_matching
  → pending_or_confirmed_seed
  → existing_follow_engine
```

首帧视觉先使用当前地图局部数据与监控帧独立求旋转、缩放、平移；再把本次内存 P1/P2 anchor 投影回监控窗口；最后按对应 memory 距离、颜色/身份、颜色面积/形状和候选置信度匹配角色。P1/P2 相对距离只能作为辅助证据。

没有独立 transform 时返回 `pending_confirmation` 或以内存 anchor 生成低置信度 seed，不能使用当前候选对拟合 transform 后把零残差当作身份确认，也不能因为第三个干扰候选直接阻断跟随。

## 实施阶段

### P0：内部计时和离线基准

文件：`src/auto_modules/features/poe2/live_terrain/experimental/multiplayer_localization/memory_anchors.py`、`src/auto_modules/features/poe2/live_terrain/player_position.py`、`src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`、`tests/poe2_live_terrain/test_multiplayer_first_frame.py`。

为 PID 查找、descriptor、reader/module、layout、entity scan、metadata、component resolve、world read、assignment、variant、shape search、post-validation 分别记录耗时和读取次数。先用 fake reader 和历史帧建立基准，不连接真实 PoE2。

验收：日志能分开进程级初始化、当前地图首帧和动态位置读取；定位结果与阈值不变。

### P1：进程级通用内存上下文

文件：`player_position.py`、`memory_anchors.py` 及对应 focused tests。

新增明确的进程 context，复用 reader、PID、创建时间、build hash、模块基址、slot RVA 和静态 layout 参数；不缓存 area、entity、Render、P1/P2 身份。PID、创建时间或 build hash 变化时完整失效。

验收：同一进程第二次首帧不重复 hash/module/build 初始化；模拟进程变化时完整重建。

### P2：当前地图首帧读取器

文件：`memory_anchors.py`、`player_position.py` 及对应 tests。

通过进程 context 解析当前 area/state 和地图数据；每次首帧重新扫描当前地图 entity vector，重新发现 P1/P2 metadata、entity、Render 地址，读取两个 Render position，生成带时间戳的 native anchors。组件名到 slot 的结果只在当前读取内复用。

验收：两张不同地图复用进程 context，但重新得到当前 area、P1/P2 identity 和位置；旧 entity 指针不能跨地图使用。

### P3：独立局部 transform

文件：`dual_first_frame.py`、`absolute_registrar.py`、`capture_test_page.py` 及 replay tests。

新增当前地图局部窗口裁剪。transform 求解只使用地图几何/墙体和监控帧，不使用当前 P1/P2 candidate pair 拟合。全局 shape registration 只作为地图变化或局部配准失败时的慢速 fallback。记录 transform 来源、局部窗口、角度、缩放、平移和耗时。

验收：替换、增加或删除角色候选不会改变独立 transform；配准耗时不随候选数量线性倍增。

### P4：以内存 anchor 为主的角色匹配

文件：`dual_first_frame.py`、`multiplayer_localization/models.py` 及 association/replay tests。

将两个 memory anchor 通过独立 transform 投影到 screen，为 P1/P2 建立独立 ROI。评分顺序固定为对应 memory 距离、颜色/身份、颜色面积/形状、候选置信度，P1/P2 相对距离只作辅助。第三候选不触发全量 6 assignment/12 variant 搜索；无法唯一决定时保留最佳 seed 和不确定性，返回 `pending_confirmation`；连续两帧确认后提交正式 seed。

验收：历史 ambiguous 帧可产生 pending/低置信度 seed；错误 pair 不能通过自拟合确认；面积异常候选不能抢角色；两帧确认后身份稳定。

### P5：接入正式首帧入口

文件：`capture_test_page.py`、`multiplayer_localization/composition.py`、`ui/modes/poe2/composition.py`。

让 `_compute_dual_first_frame()` 使用进程 context 和当前地图读取器；保持单次截图、UI 结果结构和模块化 Vision/Control/Output 所有权。pending seed 进入视觉确认链；不启用旧页面 runtime、旧 timer 或旧 output fallback。记录 memory anchor → transform → candidate → seed 的关联字段。

### P6：回归和生命周期

文件：`tests/poe2_live_terrain/test_multiplayer_first_frame.py`、`test_follow_frame_recovery_handover.py`、`test_follow_engine_stress.py`。

覆盖同一进程不同地图、重复首帧、PID/build 变化、entity/Render 变化、正常双角色、第三干扰候选、接近候选、单/零候选、pending 后确认、局部失败转全局 fallback、内存失败但视觉可用、视觉失败但内存可用、P1 恢复时 P2 不被错误 HOLD，以及 stop/restart 无 reader/worker/queue/output lease 残留。

验收顺序：纯数据测试 → 内存契约测试 → 首帧 replay → composition/lifecycle focused 测试 → 受控实机日志。必须能关联 `memory anchor → visual candidate → fused seed → target revision → intent → receipt`，否则不宣称实机完成。

## 目标和禁止事项

目标是首次首帧总耗时 ≤5s，重复首帧不重复进程初始化，截图 ≤50ms，候选提取 p95 ≤60ms，独立局部 transform p95 ≤200ms。这些是实施目标，不是当前实测结果。

禁止通过降低 `assignment_margin`、永久盲预测、跳过连续确认或增加 Python 进程数量换取延迟；不改路径、局部避障、dynamic arrival/resume/horizon、pulse、手柄参数或 Vision/Control/Output owner。

## 实施前决策门

实现前确认进程级参数清单和失效条件、首帧必读字段、独立 transform 数据源、pending seed 的允许边界、角色匹配评分优先级，以及 P0 内部计时基准已完成。
