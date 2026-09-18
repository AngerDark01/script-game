# 异步事件识别观察器

更新时间：2026-06-02

## 目标

掉落物识别包含模板、外形和颜色复核，重识别帧可能明显慢于普通导航帧。为了避免掉落物定位和人物移动定位串行阻塞，事件识别改为独立后台线程执行。

当前实现选择线程而不是独立进程，原因是小地图帧、事件配置、模板缓存和 OpenCV/Numpy 处理都在同一进程内复用成本最低；OpenCV 的重计算通常会释放 GIL，线程足以先验证卡顿是否来自识别链路。如果后续日志证明线程仍然抢占明显，再评估进程池。

## 线程边界

后台线程只做原始识别：

```text
AsyncEventObserver worker
  -> EventMonitor.detect()
  -> Portal/Loot detector.detect()
  -> 返回 EventDetection 列表
```

主导航线程仍然负责状态性逻辑：

```text
NavigationRuntimeFrameLoop
  -> poll 后台识别结果
  -> EventCoordinator.apply_detections()
  -> EventPositionStabilizer.update()
  -> EventMemory.merge_observations()
  -> EventScheduler.pick()
  -> NavigationTaskController.update_context()
  -> handler / A* / 输入执行
```

这样 `EventMemory`、`EventPositionStabilizer`、`EventScheduler`、handler 和 GUI overlay 不跨线程写，避免事件状态竞争。

## 最新帧策略

后台线程使用 latest-frame queue：

```text
主线程 submit 当前帧
  -> worker 空闲：立即处理
  -> worker 忙：pending 帧只保留最新的一帧
  -> 更旧 pending 帧被覆盖，计入 dropped_total
```

没有无界队列。掉落物重识别慢时，系统宁愿跳过旧帧，也不让过期识别任务堆积后反向拖慢导航。

## 运行时接入点

- `core/events/async_observer/runtime.py`：`AsyncEventObserver` 和 `AsyncEventDetectionResult`
- `gui/modes/navigation/runtime/loop.py`：主导航帧循环 poll/apply/submit
- `gui/modes/navigation/widget.py`：事件系统初始化、导航启动和停止时管理 observer 生命周期
- `core/events/coordinator/observation.py`：把同步 observe 拆成 detect 和 apply，供异步链路复用

## 性能日志

日志写入：

```text
logs/event_runtime.log
logs/event_runs/<session>_event_runtime.log
logs/event_runs/<session>_event_async.log
```

关键日志：

```text
async event detection result
async event detections applied
async event detection result discarded
async event observer stopped
```

字段含义：

| 字段 | 含义 |
|---|---|
| `seq` | 本次提交序号 |
| `detections` | 后台识别输出数量 |
| `detect_ms` | 后台线程实际识别耗时 |
| `detect_cpu_ms` | 后台识别线程消耗的 CPU 时间 |
| `queue_ms` | 帧提交后等待 worker 开始处理的时间 |
| `total_ms` | 从提交到识别完成的总时间 |
| `result_age_ms` | 主线程 poll 到结果时，结果已经完成多久 |
| `apply_ms` | 主线程合并 detection、稳定定位、memory merge、scheduler pick 的耗时 |
| `apply_cpu_ms` | 主线程合并阶段消耗的 CPU 时间 |
| `tasks` | 合并后事件任务数 |
| `dropped_total` | worker 忙时被新帧覆盖的 pending 帧累计数 |
| `dropped_since_last` | 距离上次性能日志新增的覆盖帧数 |
| `error` | 后台识别异常；异常不会杀死导航线程 |

日志做了节流：正常情况下约 1 秒打一条；如果识别慢、排队慢、发生丢帧或异常，会立即记录。这样可以看资源消耗，又不会因为每帧落盘制造新的卡顿。

## 验收关注点

实测时优先看三类问题：

1. `detect_ms` 经常超过导航帧间隔：说明 detector 仍重，需要继续降 full acquire 频率或改成已知目标 ROI verify。
2. `dropped_total` 快速增长且 `queue_ms` 较高：说明后台线程跟不上提交频率，但主线程没有被阻塞；可调大 `detection_interval_ms`。
3. `apply_ms` 偏高：瓶颈不在识别，而在主线程事件合并、overlay 或任务刷新。

当前掉落物正式接入仍是“后台原始识别 + 主线程状态合并”。后续如果要实现“已知掉落物只做反投影 ROI 验证”，应继续在 detector/memory 之间扩展，而不是把 memory 写入挪到后台线程。

## 掉落物命中截图

为排查误识别，`loot` 支持命中时保存当前监控区域截图。开关位于事件管理面板的 loot 参数：

```text
diagnostic_capture_enabled = true
diagnostic_stage_dump_enabled = false
diagnostic_capture_interval_ms = 500
diagnostic_capture_max_frames = 120
```

输出目录：

```text
debug/loot_runtime_diagnostics/<time_pid>/<now_ms_index>/
```

轻量模式会保存：

- `raw_minimap.png`：本次识别使用的原始小地图监控区域。
- `detection_overlay.png`：掉落物检测框、中心点和拾取半径。
- `seed_overlay.png`：存在粗检 seed 区域。
- `diagnostics.json`：检测坐标、bbox、template/shape/color 分数和当前关键参数。

`diagnostic_stage_dump_enabled=true` 时才会额外保存 `stage_raw_mask.png`、`stage_center_mask.png`、`stage_candidate_overlay.png`。这个模式会重新跑候选复核，适合短时间定位算法问题，不适合长时间实跑。
