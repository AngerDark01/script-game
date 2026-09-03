# 掉落物事件包

## 目标

`core/events/types/loot/` 是正式的掉落物拾取事件包，事件类型为 `loot`。它只从小地图识别掉落物区域，不追求逐个物品实例精确定位；多个堆叠或相邻掉落物会合并为一个可拾取 blob。事件进入导航主线后复用 A*、事件记忆、事件调度、overlay、hook 过滤和真实输入执行链路。

## 模块结构

```text
core/events/types/loot/
├── __init__.py              # 导出 LootEventDefinition
├── assets.py                # 项目内 loot 小地图模板与排除模板路径
├── config.py                # LootEventConfig typed adapter
├── definition.py            # 事件包对外定义、默认配置、GUI schema、factory
├── minimap_detector.py      # LootMinimapDetector facade
├── detection/
│   ├── models.py            # LootTemplate / LootCandidate / LootCluster DTO
│   ├── images.py            # BGR 转换、前景 mask、小图 padding 和坐标还原
│   ├── templates.py         # 模板读取、mask 构造和缩放
│   ├── scoring.py           # 颜色分数、三路加权分数、候选接受条件
│   ├── exclusions.py        # 人物箭头/玩家标记负样本排除规则
│   ├── roi.py               # 低成本存在粗检、中心人物遮罩、候选 seed/ROI 提取
│   ├── seed_scan.py         # 围绕 seed 中心做局部模板/外形/颜色复核
│   ├── clustering.py        # 候选去重、空间聚类、重叠 blob 合并
│   ├── pipeline.py          # weighted blob 检测主流程
│   ├── conversion.py        # LootCluster -> EventDetection
│   └── feature_match/       # ROI 内多特征滑窗匹配，默认异步后端使用
│       ├── models.py        # FeaturePreparedTemplate / FeatureScore DTO
│       ├── descriptors.py   # masked template、edge、Chamfer、HOG-lite 分数
│       ├── semantics.py     # 黄钻/红星/金三角语义形状门槛
│       └── matcher.py       # FeatureLootMatcher 主匹配器
├── perception/
│   ├── models.py            # 异步识别记录和定位快照 DTO
│   ├── projection.py        # local/global 坐标投影和 detection 转换
│   └── async_worker.py      # 独立线程运行 feature matcher 和缓存记录
└── handler/
    ├── runtime.py           # LootPickupHandler 状态机 facade
    ├── movement.py          # 距离到 move_to / pickup 半径判定
    ├── interaction.py       # 进入拾取半径后 press_key(pickup_key)
    └── completion.py        # 按键后等待、缺失确认、重试/失败/完成
```

正向模板资产在 `assets/event_templates/loot/minimap/`，由 `D:/ACloud/image/掉落` 复制到项目内。人物箭头负样本模板在 `assets/event_templates/loot/exclude/player_marker/`。这些 PNG 已扣成透明前景图，运行时优先用 alpha 通道作为匹配 mask，因此模板截图中多余的小地图背景不会参与模板匹配。正式运行不依赖 `D:/ACloud/image/...` 外部绝对路径。

## 识别算法

当前默认识别分成两阶段：先粗检“这一帧是否可能存在掉落物”，再在确认存在后定位掉落物区域。这样移动过程中绝大多数帧只跑低成本 mask 和连通域，不会每帧全量模板匹配。

### 2026-06-03 探针与正式接入：ROI 内多特征相似度滑窗

独立探针 `debug/loot_feature_match_probe.py` 用于验证“类似 CNN 前半段”的 ROI 内特征响应定位思路；同一套核心算法已经抽到 `detection/feature_match/`，并通过 `detector_mode=async_feature_match` 接入正式 `LootMinimapDetector`。探针和正式后端都先复用 `loot_seed_bboxes()` 找疑似区域并扣掉中心人物，再在固定大小的多锚点 ROI 窗口内对黄钻、红星、金三角模板做多尺度滑窗；每个滑窗候选计算 masked template、边缘重叠、Chamfer 距离、2x2 HOG-lite 梯度直方图、轮廓/Hu 相似度和颜色辅助分。候选不是只靠总分通过，黄钻、红星、金三角分别有语义门槛：黄钻要求菱形主体或高置信模板+HOG+Chamfer 旁路，红星排除大面积火焰块，金三角排除多凹陷伪三角。

探针默认参数必须和正式默认保持一致：`feature_match_threshold=0.64`、`feature_match_collect_threshold=0.38`、`feature_match_top_k_per_template=2`、`feature_match_max_candidates=5`、`feature_match_search_padding=48`、`feature_match_scales="0.75,0.85,1.0"`。完整样本集 `D:/ACloud/image/sample` 上的最新探针输出为 `debug/loot_feature_match_probe/20260603_174004/`：77 张样本中 TP=25、FP=0、FN=0、TN=52，平均耗时约 341.366ms，p95 约 664.686ms，最大约 680.201ms。线程并行版本墙钟略降但单张图延迟显著升高，因此正式接入采用独立 worker 线程异步执行，而不是在导航帧内直接跑完整匹配。

`LootMinimapDetector.detect(tick, config)`：

1. 读取 `tick.raw_minimap_frame`；无帧或无模板直接返回空。
2. 调用 `detection.pipeline.detect_loot_presence()` 做存在粗检。
3. 粗检内部调用 `detection.roi.loot_seed_bboxes()`：
   - 用 HSV 金色、暖色、银白、高亮构造 mask。
   - 调用 `apply_player_center_mask()` 处理固定人物位置。该函数只在小地图中心 patch 有足够亮/金/白/蓝像素，并且人物箭头负模板命中时，按 `player_center_mask_radius` 挖掉中心人物区域；这一步把人物排除前移到 mask 层，避免每个候选都跑负模板。若输入图尺寸接近单个图标，小于中心遮罩直径，会跳过该遮罩，避免把模板样本或小尺寸 probe 整张擦掉。
   - 对 mask 做 open/close/dilate、连通域面积过滤、bbox 尺寸过滤和重叠合并，得到 seed bboxes。
4. 若 `detector_mode="async_feature_match"`，先把当前 seed 交给 `AsyncLootPerception.update_visibility()` 更新已知记录的可见性，再进入异步提交/读取流程。
5. 若没有 seed，重置 presence streak；异步模式下返回空，旧 `weighted_blob` / 同步 `feature_match` 路径会清空同步缓存。
6. 若有 seed，累计 `presence_confirm_frames`。默认 `2`，即连续两帧看到疑似掉落物后才进入定位。
7. 默认异步模式下，presence 确认后调用 `AsyncLootPerception.maybe_submit()`；worker 空闲且超过 `async_full_scan_interval_ms=1000` 时复制当前帧并在后台调用 `FeatureLootMatcher.detect()`。主线程立即读取 `AsyncLootPerception.detections()` 中已有缓存；如果 worker 尚未返回，则本帧返回空，不阻塞导航循环。
8. worker 返回后，`records_from_clusters()` 把局部中心投影成全局坐标并写入缓存；后续帧只按当前 `FrameRegistration` 把缓存全局点投回局部 detection。已有记录在 `async_track_refresh_ms=8000` 内不会反复全量定位，超过 `async_track_ttl_ms=8000` 或连续缺失确认后才移除。
9. `detector_mode="feature_match"` 是同步回归/诊断模式，直接在当前帧调用 `FeatureLootMatcher.detect()`；`detector_mode="weighted_blob"` 保留旧三路加权 blob 后端，调用 `detect_loot_blobs(frame, templates, config, exclusion_templates, seed_bboxes=...)`。

2026-06-03 17:40 接入一致性验证：同一批 `D:/ACloud/image/sample` 样本用生产 `FeatureLootMatcher.detect()` 同步路径跑出 TP=25、FP=0、FN=0、TN=52；用正式默认 `LootMinimapDetector(detector_mode="async_feature_match")` 加有效 `FrameRegistration`、等待 worker 完成后也跑出 TP=25、FP=0、FN=0、TN=52。由此确认当前差异不在 feature 参数或 matcher 移植，而在调用方是否给异步 worker 留出返回窗口；测试 harness 不能把“worker 尚未返回”直接算作漏检。

`detection.pipeline.detect_loot_blobs()`：

1. 将输入帧转换为 BGR；如果测试图尺寸小于模板，则临时 padding，避免 OpenCV 模板匹配无法运行。定位复核使用原始帧，不再使用中心遮罩后的帧；中心遮罩只作用于 presence seed，避免半截人物图标绕过最终人物排除。
2. `LootMinimapDetector` 初始化时对每张模板按 `config.scales` 预生成多尺度 `LootPreparedTemplate`，默认 `0.75,0.85,1.0,1.15,1.3`。预处理内容包括缩放后的 BGR、mask、灰度图、Canny 边缘图、边缘像素数和 mask 像素数；人物箭头负样本模板也走同样的预处理，避免每帧重复 resize/Canny。模板读取时如果 PNG 有 alpha 通道，则直接把 alpha 当作前景 mask；否则才回退到 HSV/亮度/边缘推断前景。模板读取时会按 mask bbox 裁掉透明外边，避免背景 padding 参与匹配。
3. 默认启用 `roi_prefilter_enabled`。定位阶段复用 presence 阶段的 seed，不再重新全图扫 ROI。
4. `detection.seed_scan.detect_seed_candidates()` 围绕每个 seed 中心尝试少量对齐点，不生成整帧响应图。
5. 对每个 seed/template patch 计算三路局部分数：
   - `template_score`：mask 内 BGR 余弦相似度与 mask 内灰度相关分数的较高者。
   - `shape_score`：template edge 与 patch edge 在 mask 附近的边缘重合度。
   - `color_score`：金色、暖色、银白和高亮像素比例/数量，颜色只作为辅助信号。
6. 用三路加权得到最终分数：

```text
score = template_score * 0.46 + shape_score * 0.42 + color_score * 0.12
```

7. 候选接受条件默认是：

```text
score >= 0.54
color_score >= 0.12
template_score >= 0.25 或 shape_score >= 0.22
```

8. 粗检阶段的人物排除前移到中心遮罩；定位阶段只对已经 accepted 的候选再执行一次最终排除，调用 `detection.exclusions.is_player_marker_candidate()`，用人物负模板、结构分数、蓝/青底色和金白箭头形状阻断人物箭头误检。最终排除使用原始 patch，而不是中心遮罩后的 patch。
9. 通过 `detection.exclusions.is_blue_map_artifact_candidate(patch, shape_score)` 过滤高蓝底、低金色、亮白区域偏多且外形分数不足的地图装饰/边线类候选。当前增加了蓝白装饰分支：蓝底比例高、金色接近 0、白/亮区域偏多且外形不足时直接排除。1b2a 这类真实掉落物虽然可能有蓝底，但仍保留明显金色或更好的外形信号，因此不会被该规则误杀。
10. 通过 `clustering.cluster_candidates()` 把重叠、中心点接近、堆叠的候选合并为 `LootCluster`。
11. 还原 padding 前坐标，输出最多 `max_blobs_per_frame` 个 blob。

检测输出不是“物品列表”，而是“可拾取区域”。`conversion.clusters_to_detections()` 会把 blob center 写入 `EventDetection.local_minimap_pos`，把 bbox、候选数、命中模板、三路分数和 `pickup_radius` 写入 metadata。

## 事件定位与目标锁定

掉落物事件不会触发 `NavigationCore` 的全图定位。事件定位链路只做局部点投影：

```text
LootMinimapDetector.detect()
  -> EventDetection.local_minimap_pos
  -> EventPositionStabilizer.project_detection()
  -> global = frame_registration.frame_origin_global + local_minimap_pos * draw_scale
  -> EventMemory.merge_observations()
  -> EventTask.global_pos
```

这里依赖的是当前帧已有的 `FrameRegistration`，不会重新跑地图模板全局搜索。移动时如果感觉“像一直重定位”，通常不是人物定位被事件改坏，而是掉落物 blob center 在多帧中漂移：堆叠图标、部分遮挡、小地图动画和候选合并都会让中心点变化。旧行为在 `EventTask.mark_seen()` 中每次稳定观测都覆盖 `task.global_pos`，随后 `NavigationTaskBuilder` 会把新 `global_pos` 变成新的 event navigation target，`MovementExecutor.ensure_movement_path()` 看到目标变化后可能重跑 A*，表现为卡顿和频繁改目标。

当前默认策略在 memory 层处理，而不是改 detector：

```text
EventMemory.merge_observations()
  -> should_update_task_target(task, observation, event_config)
  -> loot target_update_mode = lock_after_confirm
  -> task 已确认后不再覆盖 global_pos
  -> 仍刷新 last_seen_ms / confidence / seen_count / metadata / last_observed_global_pos
```

这样 `task.global_pos` 作为导航目标保持稳定，消失确认仍能依赖 `task.last_seen_ms` 判断是否被继续观测到。`last_observed_global_pos` 保留最新投影点，方便日志诊断真实检测漂移。2026-06-09 起，portal 也恢复锁点语义，默认使用 `limited_after_confirm`，确认后只接受小范围漂移更新，避免传送门候选在相邻稳定簇之间跳动时拖动导航目标。

YOLO 的定位速度与精度不是当前优先解法。即使换成 YOLO，也仍会输出一个检测框/中心点，后续仍要经过同样的投影、稳定、memory 合并和导航目标策略；如果目标点继续每帧覆盖，A* 重规划问题仍存在。YOLO 只有在模板/外形/颜色三路识别无法覆盖更多真实掉落物样式时，才适合作为 detector backend 候选。

## 2026-06-01 设计记录：只定位少数帧，后续按地图记忆复用

状态：设计讨论已确认方向，尚未作为完整 runtime 策略落地。当前探针和 detector 仍用于样本验证；正式融合前需要用用户收集的小地图样本再做一轮回归。

### 问题判断

掉落物事件的资源消耗不应该来自导航执行或按 A，而主要来自“反复定位”。如果每帧都对整张小地图做模板/形状/颜色复核，人物移动时会持续触发昂贵检测，多个掉落物同时存在时成本会继续放大。更合理的模型是：

```text
昂贵定位 = 只用于首次发现/确认新掉落物
后续导航 = 使用已投影到地图上的 global_pos
后续确认 = 使用反投影到当前小地图的小 ROI，而不是全图重新定位
```

### 目标策略

采用 `acquire once, navigate by memory, verify cheaply`：

1. **首次发现严格**：用 presence 粗检连续 2-3 帧确认，再执行一次较贵的 `detect_loot_blobs()`，得到 `local_minimap_pos`。
2. **坐标投影入库**：通过当前 `FrameRegistration.frame_origin_global + local_minimap_pos * draw_scale` 转成 `global_pos`，写入 `LootMemory/EventMemory`。
3. **目标锁定**：一旦 task 被确认，`task.global_pos` 不再被每帧观测覆盖；后续只刷新 `last_seen_ms`、`confidence`、`seen_count`、`metadata` 和 `last_observed_global_pos`。
4. **地图标记复用**：导航地图上保留 loot marker，调度器直接按 `global_pos` 选择和靠近目标，不因小地图图标中心抖动而重跑 A*。
5. **反投影小 ROI 确认**：人物移动后，用当前 `FrameRegistration` 把已知 `global_pos` 反投影回当前小地图局部坐标，只在预期位置附近裁剪小窗口做确认。
6. **消失确认保守**：如果目标按全局坐标推算应该在当前小地图范围内，但小 ROI 连续 N 次没有掉落物特征，才认为已拾取/消失；一帧漏检不删除 task。

### 预计运行状态机

```text
无已知 loot
  -> 低频 full acquire，例如 600-1000ms 一次
  -> presence 连续 2-3 帧
  -> detect_loot_blobs 定位一次
  -> 写入 memory，创建地图 marker

已有 pending/running loot
  -> 不对该目标重复全图定位
  -> 用 global_pos 反投影 expected_local_pos
  -> expected_local_pos 在小地图内时做 ROI verify
  -> ROI 存在：刷新 last_seen_ms
  -> ROI 连续缺失：complete/disappeared

正在拾取当前 loot
  -> 降低或暂停新目标 full acquire
  -> 到 pickup_radius 后按 pickup_key
  -> 等待 post_pickup_wait_ms
  -> 对当前目标做 projected ROI verify
  -> 连续缺失后 complete，否则有限次数重试
```

### 核心算法草图

全局坐标反投影：

```text
expected_local_x = (task.global_x - frame_origin_global_x) / draw_scale
expected_local_y = (task.global_y - frame_origin_global_y) / draw_scale
```

Projected ROI verify：

```text
输入：frame, expected_local_pos, verify_radius
1. 若 expected_local_pos 不在当前小地图范围，跳过图像确认，只保留 memory。
2. 裁剪 expected_local_pos 周围 radius=30-45px 的 ROI。
3. 对 ROI 运行轻量 seed mask 和连通域过滤。
4. 若没有合理连通域，记一次 missing。
5. 若有连通域，可选只对 1-2 个最佳 seed 做局部模板/形状复核。
6. 通过则刷新 task.last_seen_ms；不通过则累计 missing_seen。
```

这里的 ROI verify 是“确认已知目标还在”，不是“发现新目标”，因此阈值可以比首次 acquire 宽松，但删除/完成必须更保守。

### 多掉落物处理

一次 full acquire 可能产出多个 cluster。正确行为是批量写入 memory：

```text
detect_loot_blobs -> clusters
clusters -> global_pos list
merge with existing memory by dedupe_radius
new cluster -> create pending task
existing cluster -> refresh observation only
```

后续由导航任务调度器按距离、优先级、状态选择一个 loot 任务；其他 loot 作为地图 marker 保留，不因为“掉落物很多”就每帧重新定位所有目标。

### 资源消耗预期

当前探针量级：

| 操作 | 预期耗时 |
|---|---:|
| presence 粗检/空帧 | 约 1-2ms |
| full acquire 有候选 | 平均约 9-10ms，峰值可能 40-50ms |
| projected ROI verify | 目标 <1-3ms |
| memory 坐标判断/去重 | 接近可忽略 |

因此后续优化重点不是直接换 YOLO，而是降低 full acquire 频率，并把已知目标的持续确认改成 projected ROI verify。即使未来 detector backend 换成 YOLO，memory、反投影和目标锁定策略仍应保留。

## 执行流程

完整链路：

```text
GUI frame loop
  -> EventCoordinator.observe()
  -> EventMonitor.detect()
  -> LootMinimapDetector.detect()
  -> detect_loot_presence()
  -> detect_loot_blobs()
  -> EventPositionStabilizer.update()
  -> EventMemory.merge_observations()
  -> NavigationTaskBuilder.build()
  -> NavigationTaskScheduler.pick()
  -> EventApproachController.update()
  -> EventCoordinator.run_task()
  -> LootPickupHandler.update()
  -> EventAction.move_to / press_key / wait / complete / fail
  -> NavigationTaskController turns EventAction into NavigationIntent
  -> GUI input runtime executes MOVE_MAP or PRESS_KEY
```

`NavigationTaskBuilder` 会读取 loot task metadata 中的 `pickup_radius`，写入 navigation task 的 `event_stop_radius`。因此通用 `EventApproachController` 不是固定贴到 `event_stop_radius=18` 才释放 handler，而是对 loot 使用当前配置的拾取半径释放。这样 `pickup_radius` 同时控制两件事：

- 导航层何时允许 handler 接管并准备按 A。
- handler 内部何时从 `move_to` 切换到 `press_key(pickup_key)`。

## Handler 状态机

`LootPickupHandler`：

1. `move_near_loot`：如果没有定位，返回 `WAIT`。
2. 距离大于 `arrival_radius`：返回 `EventAction.move_to(task.global_pos)`。
3. 距离大于 `pickup_radius`：继续 `move_to`，metadata 带 `force_repeat_click=True`。
4. 进入 `pickup_radius`：返回 `EventAction.press_key(pickup_key)`，默认 `a`。
5. `wait_result`：等待 `post_pickup_wait_ms`。
6. 如果 `tick.now_ms - task.last_seen_ms` 超过 `absence_confirm_frames * absence_frame_ms`，认为小地图上该 blob 已消失，返回 `COMPLETE`。
7. 如果仍被观测到且未超过 `pickup_press_limit`，短等待后回到靠近/拾取状态，下一帧可再次按键。
8. 超过按键次数后返回 `FAIL`，由 `EventRunner` 根据 `retry_limit` 和 memory 策略重试或忽略。

完成后 `EventRunner` 会调用 `EventMemory.mark_completed()` 和 `suppress_nearby_pending()`，因此附近残留的同类 pending loot task 会被 suppression，避免一堆堆叠图标造成重复任务。

## 配置参数

关键参数在 `LootEventConfig`，并通过事件管理 GUI schema 暴露：

| 参数 | 默认 | 作用 |
|---|---:|---|
| `priority` | 60 | 与 portal 等事件调度排序，portal 默认 100，loot 默认较低 |
| `weighted_threshold` | 0.54 | 三路加权接受阈值 |
| `collect_threshold` | 0.28 | 宽松候选收集阈值 |
| `detection_interval_ms` | 450 | detector 实际扫描间隔；间隔内默认复用上一帧 detection，降低持续 CPU 占用 |
| `reuse_previous_detections` | true | 是否在扫描间隔内返回重新打时间戳的缓存 detection |
| `presence_confirm_frames` | 2 | 粗检连续存在多少帧后才进入定位复核，降低移动中偶发噪声和每帧全量定位 |
| `masked_color_match_enabled` | true | 是否对已命中的候选 patch 做局部 mask 彩色补分；当前不是 full-frame masked 匹配 |
| `roi_prefilter_enabled` | true | 是否先用颜色/亮度连通域找 ROI，再在 ROI 内做模板/外形匹配 |
| `roi_min_area` | 12 | ROI 连通域最小面积，过小噪声直接忽略 |
| `roi_max_size` | 150 | ROI 原始连通域最大宽高，避免大块 UI/背景进入重匹配 |
| `roi_expand` | 48 | ROI bbox 扩张像素，给模板匹配保留周边上下文 |
| `template_weight` | 0.46 | 模板匹配权重，掉落物识别的第一主信号 |
| `shape_weight` | 0.42 | Canny 外形匹配权重，掉落物识别的第二主信号 |
| `color_weight` | 0.12 | 颜色/亮度辅助权重，避免黄色/白色图标单靠颜色过线 |
| `player_marker_exclusion_enabled` | true | 是否启用人物箭头/玩家标记排除 |
| `player_marker_template_threshold` | 0.75 | 普通人物箭头负模板阈值；GUI 可调，实际排除还需要结构分数保护，避免真实掉落物被颜色相似度误杀 |
| `player_marker_exact_template_threshold` | 0.96 | exact 级人物箭头负模板命中的排除阈值；仍需要最低结构分数 |
| `player_marker_blue_ratio_threshold` | 0.30 | 玩家底色蓝/青色像素比例阈值 |
| `player_marker_triangle_score_threshold` | 0.54 | 人物箭头金白区域三角/箭头外形阈值 |
| `player_center_mask_enabled` | true | 是否启用小地图中心人物遮罩；默认用于替代每个候选的人物负模板重匹配 |
| `player_center_mask_overlay_enabled` | true | 是否在导航地图 overlay 上显示中心人物遮罩范围；只影响调参显示，不参与识别 |
| `player_center_mask_radius` | 28 | 中心人物擦除半径，单位为小地图像素；仅在中心 patch 被确认像人物箭头时生效，事件面板已用中文标签和 tooltip 暴露，觉得遮罩过大时优先调小该值 |
| `max_blobs_per_frame` | 3 | 每帧最多输出的掉落物区域 |
| `stable_frames` | 2 | 跨帧稳定后才生成 observation |
| `localization_cluster_radius` | 72 | 小地图局部坐标投影到全局坐标后的稳定聚类半径 |
| `dedupe_radius` | 110 | memory 合并同一 loot task 的半径 |
| `target_update_mode` | lock_after_confirm | task 确认后锁定 `global_pos`，避免 blob center 漂移拖动导航目标 |
| `target_update_max_drift` | 0 | `limited_after_confirm` 模式下围绕首次锁定点允许校正的最大漂移；默认锁定模式不使用 |
| `arrival_radius` | 90 | 开始进入拾取接近阶段的距离 |
| `pickup_radius` | 58 | 拾取半径，同时影响 event approach 释放半径 |
| `pickup_key` | a | 拾取按键 |
| `post_pickup_wait_ms` | 450 | 按键后等待小地图刷新 |
| `absence_confirm_frames` | 2 | 连续缺失确认帧数 |
| `pickup_press_limit` | 3 | 同一 task 最多按键次数 |
| `cooldown_radius` | 180 | 完成后 suppression/cooldown 半径 |
| `diagnostic_capture_enabled` | false | 是否在正式运行时保存掉落物诊断采样；默认关闭，避免持续落盘和额外复核开销 |
| `diagnostic_capture_interval_ms` | 1000 | 诊断采样最小间隔，只在开启且有 detection 时生效 |
| `diagnostic_capture_max_frames` | 50 | 单次运行最多保存多少组诊断采样 |

事件管理窗口的“事件参数”页由 `LootEventDefinition.config_schema()` 驱动。顶部用下拉框选择完整事件，并通过“启用当前事件”开关控制该事件是否参与识别；下方的大滚动区域渲染所有可编辑参数，包括识别阈值、三路权重、ROI 预筛、人物中心遮罩、拾取半径/按键、目标锁定策略以及诊断采样开关。2026-06-04 起，GUI 参数渲染支持 schema 的 `help` 字段；`player_center_mask_enabled`、`player_center_mask_overlay_enabled` 和 `player_center_mask_radius` 已改为中文标签并带说明，用户可直接在前端调中心人物擦除半径，并决定是否在导航地图 overlay 上显示该范围。`build_tui_event_options()` 会先把事件定义默认值与当前地图 `event_config.json` 合并，再交给 GUI 渲染，因此旧地图即使尚未保存过 `events.loot`，也能在面板中看到完整参数；点击“保存配置”后写回当前地图的 `event_config.json`。实时任务列表已经移到独立的“触发状态”页，避免压缩参数调试空间。

运行时诊断采样写入 `debug/loot_runtime_diagnostics/<time_pid>/...`。采样内容包括原始小地图、粗检 mask、人物中心遮罩后的 mask、seed overlay、candidate overlay 和 `diagnostics.json`。该开关只用于排查误识别/漏识别，平时应保持关闭；需要现场分析时，在事件管理面板中打开 `diagnostic_capture_enabled`，并根据卡顿情况调大 `diagnostic_capture_interval_ms` 或调小 `diagnostic_capture_max_frames`。

兼容迁移：如果旧地图的 `event_config.json` 已经保存过 loot 配置，但还没有 `roi_prefilter_enabled` 字段，`EventSystemConfig.from_dict()` 和 `LootEventConfig.from_dict()` 会把 `detection_interval_ms`、`reuse_previous_detections`、`presence_confirm_frames`、`masked_color_match_enabled`、`roi_*`、`player_center_mask_*` 自动迁移到当前性能默认。显式带有 `roi_prefilter_enabled` 的新配置仍保留用户选择。

## 单独验证

正式探针位于 `debug/loot_event_probe.py`，直接调用 production detector 和 handler：

```powershell
D:\ACloud\.venv\Scripts\python.exe debug\loot_event_probe.py --handler-smoke
```

数据集评估脚本位于 `debug/loot_dataset_eval.py`，用于批量验证已标注小地图样本，而不是只测单张探针图：

```powershell
D:\ACloud\.venv\Scripts\python.exe debug\loot_dataset_eval.py --dataset-root D:\ACloud\image\sample --map-config map_data\A\event_config.json
```

输入目录约定：

- `D:\ACloud\image\sample\02_has_loot`：期望检测到掉落物。
- `D:\ACloud\image\sample\03_no_loot`：期望不检测到掉落物。

脚本行为：

- 从 `map_data/A/event_config.json` 读取 `events.loot` 运行配置，默认关闭 runtime diagnostic 落盘，只测 detector 本身。
- 每张图单独创建新的 `LootMinimapDetector`，按 `presence_confirm_frames` 连续喂同一帧，避免 detector 缓存或 presence streak 在样本之间串扰。
- 输出 `summary.json`、`cases.csv`，并默认只保存 FP/FN 的 overlay；使用 `--dump-all` 可以保存全部样本 overlay。
- 默认即使有 FP/FN 也返回 0，便于先收集基线；加 `--strict` 后有误检或漏检会返回非 0，适合后续做回归门禁。
- 常用覆盖参数：`--threshold`、`--collect-threshold`、`--presence-confirm-frames`、`--player-center-mask-radius`、`--max-blobs-per-frame`。

2026-06-03 首轮数据集基线：

```text
样本：total=77，has_loot=25，no_loot=52
结果：TP=25，FP=52，FN=0，TN=0
指标：precision=0.3247，recall=1.0000，false_positive_rate=1.0000，accuracy=0.3247
耗时：avg=215.747ms，p50=208.257ms，p95=418.551ms，max=485.987ms
输出：debug/loot_dataset_eval/20260603_104108/
```

该基线说明：当前正样本召回足够，但负样本全部误检。误检样本的 best confidence 分布约为 `0.5423` 到 `0.6626`，低于地图 A 当前 `weighted_threshold=0.70`；因此后续优化重点不应只调高全局阈值，而应审计 `detection.scoring.accepted_candidate()` 中的 `strong_gold_icon_candidate()` / `strong_neutral_icon_candidate()` 直通条件，以及 accepted 后的 artifact / player marker 排除规则。

2026-06-03 新增图片级 presence 探针 `debug/loot_presence_eval.py`。它不改 runtime detector，而是从整张小地图提取 HSV 区域统计、黄色/红色连通域统计和 production 候选统计，再用 OpenCV RTrees 训练一个图片级二分类 probe，用来回答“这张小地图是否有掉落物”：

```powershell
D:\ACloud\.venv\Scripts\python.exe debug\loot_presence_eval.py --dataset-root D:\ACloud\image\sample --map-config map_data\A\event_config.json --save-model
```

本轮输出：`debug/loot_presence_eval/20260603_113109/`。

```text
train_eval: TP=25 FP=0 FN=0 TN=52，precision=1.0，recall=1.0，FPR=0.0，accuracy=1.0
cross_validation: TP=19 FP=1 FN=6 TN=51，precision=0.95，recall=0.76，FPR=0.0192，accuracy=0.9091
```

解释：训练集自测 77/77 全对，只说明当前已标注样本可以被图片级特征区分；5 折交叉验证仍漏掉 6 张正样本并误判 1 张负样本，因此该模型当前只能作为 presence 探针和调参参考，不能直接作为最终 runtime 判定。下一步应优先分析交叉验证漏召回样本 `006`、`021`、`039`、`042`、`052`、`075`，把其中稳定视觉规律沉淀为规则或补充正模板/正样本，而不是只依赖训练集记忆。

2026-06-03 12:17 更新：`debug/loot_presence_eval.py` 已补充随机 CV、按采样批次 grouped CV、`sample_diagnostics.csv`、误判 contact sheet，并增加 `--feature-set baseline|fusion`。默认 `baseline` 仍使用低维图片级特征：HSV 区域统计、warm 连通域几何、production 候选中的 template/shape/color/exclusion 汇总。`fusion` 会额外把中心扣除、neutral/bright 组件和轮廓形状特征送入模型，但在当前小数据集上更容易过拟合，因此只作为实验选项，不作为默认。

```powershell
D:\ACloud\.venv\Scripts\python.exe debug\loot_presence_eval.py --dataset-root D:\ACloud\image\sample --map-config map_data\A\event_config.json --save-model
D:\ACloud\.venv\Scripts\python.exe debug\loot_presence_eval.py --dataset-root D:\ACloud\image\sample --map-config map_data\A\event_config.json --feature-set fusion
```

本轮默认 baseline 输出：`debug/loot_presence_eval/20260603_121751/`。

```text
train_eval: TP=25 FP=0 FN=0 TN=52，precision=1.0，recall=1.0，FPR=0.0，accuracy=1.0
random 5-fold CV: TP=19 FP=2 FN=6 TN=50，precision=0.9048，recall=0.76，FPR=0.0385，accuracy=0.8961
grouped CV: TP=15 FP=6 FN=10 TN=46，precision=0.7143，recall=0.6，FPR=0.1154，accuracy=0.7922
```

结论：
- 当前探针不是纯颜色算法；默认 baseline 已包含颜色、连通域几何、模板分数、边缘形状分数和人物/蓝白装饰排除统计。
- 训练集全对不能作为接入 runtime 的依据。随机 CV 仍漏掉 `006`、`021`、`039`、`042`、`052`、`075`，误判 `057`、`061`；grouped CV 暴露跨采样批次泛化更弱。
- 高维 `fusion` 特征在本轮实验中把随机 CV 拉低到 `TP=16 FP=2 FN=9 TN=50`，grouped CV 拉低到 `TP=14 FP=20 FN=11 TN=32`，说明“加更多特征”会让小样本模型记住局部背景，不应默认启用。
- 误判形态主要有两类：真实掉落物贴近人物或位于边缘时容易被中心遮罩/边缘策略削弱；负样本中的人物箭头、蓝色事件、问号、战斗数字和半透明地图背景会产生类似颜色与模板响应。
- 后续优化方向应是图标级规则而不是继续堆全图特征：用人物箭头模板/小半径中心扣除替代大圆直接抹除；对 4x4、6x6 小噪声提高轮廓面积下限；对灰色钻石模板增加更强的蓝白地图线排除；把边缘区域降权而不是直接排除。

性能基准：

```powershell
D:\ACloud\.venv\Scripts\python.exe debug\loot_event_probe.py --benchmark --handler-smoke
```

目标漂移回归：

```powershell
D:\ACloud\.venv\Scripts\python.exe debug\loot_event_probe.py --target-jitter-smoke
```

该探针会连续向 `EventMemory` 喂入同一个 loot 的多个漂移 observation。期望结果是 `target_locked=true`，`task.global_pos` 保持首次目标，同时 `last_observed_global_pos` 继续更新。

指定单图：

```powershell
D:\ACloud\.venv\Scripts\python.exe debug\loot_event_probe.py --image D:\ACloud\image\test\xxx.png --handler-smoke
```

断言式单图回归：

```powershell
D:\ACloud\.venv\Scripts\python.exe debug\loot_event_probe.py --image D:\ACloud\image\test\1b2a3a7e-34fd-453d-8e4f-ecb7cbe99cc5.png --dump-stages --expect-count 1 --expect-center 173,112 --center-tolerance 8
```

负样本断言：

```powershell
D:\ACloud\.venv\Scripts\python.exe debug\loot_event_probe.py --image D:\ACloud\image\人物\0b799b87-9b87-4458-b026-5d7df13da763.png --expect-count 0
```

常用调参：

```powershell
D:\ACloud\.venv\Scripts\python.exe debug\loot_event_probe.py --threshold 0.50 --pickup-radius 72 --handler-smoke
```

输出：

- JSON：每张图的 detection 数、中心点、bbox、三路分数、pickup_radius。
- 标注图：`debug/loot_event_probe/<image_stem>/loot_overlay.png`。
- `--dump-stages`：额外输出 raw mask、center mask、seed overlay、candidate overlay 和候选分数；小尺寸样本会按 production padding 路径运行后再还原坐标。
- `--expect-count` / `--expect-min-count` / `--expect-center`：探针断言，不满足时进程返回非 0，适合做回归测试。
- handler smoke：验证 `move_to -> press_key(a) -> wait -> complete`。
- benchmark：输出 `positive_tiny`、`blank300`、`positive300`、`player300` 的平均耗时、峰值耗时和 detection 数。

本轮已验证的误判回归：

```powershell
D:\ACloud\.venv\Scripts\python.exe debug\loot_event_probe.py --image D:\ACloud\image\人物\0b799b87-9b87-4458-b026-5d7df13da763.png
```

期望结果：`detection_count=0`，即人物箭头不再被识别成掉落物。

本轮性能回归数据：

| 场景 | 优化前均值 | 优化后默认均值 | 强制每帧扫描均值 | 结果 |
|---|---:|---:|---:|---|
| `positive_tiny` | - | 约 9.52 ms | 峰值约 38.56 ms | 1 detection |
| `blank300` | 约 1248 ms | 约 1.55 ms | 约 3 ms 峰值 | 0 detection |
| `positive300` | 约 1269 ms | 约 9.05 ms | 峰值约 48.99 ms，间隔内复用 | 1 detection |
| `player300` | 约 1272 ms | 约 1.15 ms | 峰值约 1.32 ms | 0 detection |

## 2026-06-03 15:06 灰钻误检与 seed 定位优化

背景：生产定位器在 `D:/ACloud/image/sample` 数据集上的基线为 `TP=25 FP=52 FN=0 TN=0`，说明召回足够但负样本全部误检。FP 裁剪分析显示，主要误检来自灰钻模板 `fef5a19f6713c9f973263eb8fbcff1a4` 吸附地图柱、蓝色事件图标、路线边缘和场景高亮；少量误检来自黄钻、红星、剑、大金币模板在火焰/箭头/背景块上触发。

本轮修复点：

- `seed_scan._best_candidate_for_seed()` 不再只用 seed 中心点。对较大的 seed bbox 生成最多 9 个网格锚点，再在每个锚点周围做小偏移匹配。这样同一大 seed 内的真实黄钻不会被中心附近的地图柱抢走。典型样本 `045`、`046` 的 overlay 已从地图柱定位修正到黄钻附近。
- 候选排除前移到候选评分阶段。每个候选先经过人物、灰钻、黄钻、剑、大金币、黄三角、红星、蓝色地图 artifact、白色路线环等 veto 后，再参与排序。这样最高分伪目标被排除后，同 seed 内的次优真实候选可以接手。
- 新增灰钻模板专用 veto：只对 `fef5a19...` 生效，用 `template_score/shape_score/gold/red/blue/white/bright` 组合识别地图柱、蓝底白灰柱、低亮度路线块、中等红色场景块等伪目标。
- 新增模板专用几何 veto：黄钻要求紧凑金色主体；剑要求长条金色主体且低红色背景；大金币拒绝火焰/红色背景；黄三角拒绝红色场景块；红星要求中等大小、紧凑、近似星形/圆形的红色主体。

验证命令：

```powershell
D:\ACloud\.venv\Scripts\python.exe -m py_compile core\events\types\loot\detection\exclusions.py core\events\types\loot\detection\seed_scan.py core\events\types\loot\detection\pipeline.py
D:\ACloud\.venv\Scripts\python.exe debug\loot_dataset_eval.py --dataset-root D:\ACloud\image\sample --map-config map_data\A\event_config.json --dump-all
```

最新输出：`debug/loot_dataset_eval/20260603_150637/`。

```text
samples: total=77 has_loot=25 no_loot=52
counts: TP=25 FP=8 FN=0 TN=44
metrics: precision=0.7576 recall=1.0000 fpr=0.1538 accuracy=0.8961
timing: avg=267.803ms p50=257.646ms p95=448.294ms max=655.84ms
```

剩余 FP：`019`、`030`、`033`、`036`、`038`、`056`、`065`、`067`。这些仍主要是灰钻模板命中蓝色事件/地图柱/路线边界。最新 TP/FP 裁剪搜索中，继续压低这 8 个 FP 只能依赖非常窄的阈值组合，容易误伤后续真实蓝底/灰色掉落样本，因此本轮停止继续堆规则。后续若要继续优化，应优先补充人工确认的定位级标注，而不是只用图片级有/无标签。

2026-06-03 15:43 定位审计补充：上面的 `TP/FN/TN/FP` 是图片级分类指标，只回答“这张图有没有任意 detection”，不回答“detection 是否框到真实掉落”。用户复查 `021` 后确认存在 `TP` 但定点错误的情况：战斗数字/地图柱/蓝色图标会被框到，而真实掉落没有成为最终目标。已新增定位审计工具：

```powershell
D:\ACloud\.venv\Scripts\python.exe debug\loot_localization_audit.py --run-dir debug\loot_dataset_eval\20260603_154352 --label has_loot
```

输出：

- `localization_audit/detections_contact_sheet.png`：每个正样本 detection 的实际裁剪，适合人工标注“对/错”。
- `localization_audit/detections.csv`：每个 detection 的 sample、center、bbox、template、confidence、template/shape/color 分数。

当前定位审计发现的典型错框：`021 #0`、`039 #0`、`040 #0`、`042 #0`、`052 #0`、`075 #0` 等灰柱/蓝色图标/战斗 UI。一次过严实验尝试把灰钻无金色主体、黄钻小面积主体直接拒绝，结果从 `TP=25 FP=8 FN=0` 变为 `TP=20 FP=4 FN=5`，把 `021/039/042/052/075` 直接打成漏检。因此不能继续靠图片级标签硬调阈值；后续应建立定位级标注集，例如对每张正样本给出正确掉落 bbox/center，或至少在 `detections_contact_sheet.png` 上标出哪些 detection 是错框。

## 风险

- 当前识别已验证 `D:/ACloud/image/test` 三张正样本、`D:/ACloud/image/人物/0b799...` 人物样本，以及 `D:/ACloud/image/957...`、`bc314...`、`fd461...` 三张旧误判负样本；其中 `1b2a...` 当前 production detector 的稳定检测中心为 `(173,112)`。真实游戏小地图缩放、压缩、光照和 UI 动画仍可能需要继续调 `weighted_threshold` / `collect_threshold`。
- 人物箭头排除当前只有 1 张负样本模板，运行时会预处理成多个尺度。默认路径先对小地图中心做人物遮罩，再对 accepted 候选做最终排除；如果后续角色朝向、缩放、皮肤或小地图底色变化导致中心遮罩或候选排除失效，需要继续向 `assets/event_templates/loot/exclude/player_marker/` 增加负样本，或调高/调低 `player_center_mask_radius` / `player_marker_*` 参数。
- 蓝底 artifact 过滤依赖 `blue_ratio/gold_ratio/bright_ratio/shape_score` 的组合阈值。它目前保留 1b2a 真实掉落物并排除旧人物/地图装饰负样本，但如果未来出现“蓝底、无金色、外形分数低”的真实掉落物，需要降低该过滤强度或增加正向模板。
- 如果掉落物正好压在小地图中心人物箭头下方，中心遮罩会优先保人物过滤，可能漏掉中心附近的掉落物；实际拾取范围较大时通常可接受，若要识别中心重叠物，需要后续做“人物模板扣除后再检测残留”的专门逻辑。
- ROI 预筛依赖掉落物局部存在金色、暖色、银白或高亮像素。若后续出现暗色掉落物图标，可能需要扩展 `build_loot_roi_mask()` 的颜色范围或暂时关闭 `roi_prefilter_enabled` 做诊断。
- `detection_interval_ms` 缓存会在短间隔内复用上一帧 detection，理论上会让已拾取物品最多延迟一个扫描间隔才从 overlay 消失；当前默认 450ms，handler 的缺失确认仍由 `task.last_seen_ms` 和后续实际扫描驱动。
- 缺失确认依赖 `task.last_seen_ms` 及时更新；因此 loot 默认把 `localization_emit_interval_ms` 调短为 150ms，避免因稳定观测节流过长造成误完成。
- loot 默认确认后锁定导航目标。如果真实场景中首次 blob center 明显偏离可拾取区域中心，可以把 `target_update_mode` 临时调为 `limited_after_confirm` 并给 `target_update_max_drift` 一个小值做诊断；不要直接改成 `continuous`，否则会重新引入移动中目标漂移和 A* 重规划风险。
- Loot 默认优先级 60，portal 默认 100；如果用户希望“看见掉落物优先捡”，应提高 loot priority。
- `pickup_key` 当前 GUI schema 是 choice，不是任意字符串输入；需要更多键位时要扩展 GUI 参数控件或增加 choices。
