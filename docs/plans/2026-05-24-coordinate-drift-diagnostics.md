# 坐标失准诊断与重新匹配方案

## 当前目标

先把坐标失准从导航/事件混合日志中拆出来，形成独立证据链。当前版本只做诊断，不自动改变导航行为，避免在未确认根因前引入新的路径冲突。

独立日志文件：

```text
logs/coordinate_diagnostics.log
```

## 需要记录的关键坐标

- `raw`：`NavigationCore.localize()` 本帧直接输出的全局坐标。
- `trusted`：`NavigationTaskController.observe_localization()` 接受后的可信坐标。
- `control`：用于导航判定和点击映射的平滑控制坐标。
- `target`：当前任务目标，可能是必经点、出口或事件点。
- `reg_*`：当前帧墙体配准结果，包括 `reg_source`、`reg_conf`、`reg_origin`、`reg_local`、`reg_meta`。
- `route_deviation`：`control` 投影到辅助锚点路线后的偏离距离。

## 失准识别信号

1. `localization invalid`
   - 本帧没有有效定位，或置信度低于导航控制器阈值。
   - 重点看 `reg_source`，例如 `template_match_failed`、`jump_rejected`、`low_features`。

2. `raw localization jump`
   - 本帧 `raw` 相对上一帧突跳过大。
   - 如果同时 `reg_conf` 不高，通常说明局部跟踪或模板匹配发生错配。

3. `raw control gap`
   - `raw` 与 `control` 距离过大。
   - 可能是平滑滞后，也可能是 raw 突然错配，需要结合 `reg_source/reg_conf` 判断。

4. `route projection deviation`
   - `control` 明显偏离用户锚点路线。
   - 如果游戏画面里人物实际在路线上，说明定位或坐标映射可能偏了。

5. `arrival mismatch raw inside control outside`
   - `raw` 已进入目标半径，但 `control` 还没进入。
   - 这类问题通常会造成“已经到了但必经点/事件不完成”。

6. `near target not completed`
   - `control` 长时间停在目标附近，但没有进入完成半径。
   - 重点用于判断目标点不可站立、完成半径过小、或坐标存在稳定偏差。

## 自动重新匹配流程

当前版本已经从“只诊断”升级为内部恢复机制。它不是业务事件，不进入 `EventCoordinator`，而是在导航控制器内作为坐标恢复事件处理。

1. 软触发
   - 连续出现 `route projection deviation`、`raw control gap` 或 `near target not completed`。
   - 只对 `reg_source=f2f` 的帧计入恢复分数，避免模板匹配帧被误判。
   - 默认 `recovery_window_ms=2600`、`recovery_score_threshold=3`、`recovery_cooldown_ms=4500`。

2. 暂停点击
   - `NavigationTaskController` 返回 `WAIT` 意图，并带上 `metadata.force_relocalize=True`。
   - `NavigationModeWidget` 收到后不执行移动点击，避免错位时继续扩大偏差。

3. 强制全局匹配
   - 调用 `NavigationCore.request_global_relocalization(reason)`。
   - 清空 `is_localized/prev_wall_mask/prev_mask`。
   - 下一帧不使用 F2F 和局部窗口，直接用完整 `wall_layer` 做模板匹配。

4. 接受新定位
   - 强制全局匹配使用更高阈值 `force_global_min_confidence=0.82`。
   - 接受后把 `trusted/control` 硬重置到新坐标，并重置 `MovementExecutor`。

5. 拒绝新定位
   - 如果全局匹配置信度不足，会继续处于未定位/全局搜索状态，不回到 F2F 漂移链。
   - `logs/coordinate_diagnostics.log` 会打印 `coordinate relocalization rejected`。

6. 恢复导航
   - 重匹配成功后打印 `coordinate relocalization accepted` 和 `nav coordinate relocalization accepted`。
   - 下一帧重新选择当前任务和路径，不沿用漂移期间的旧路径。

## 当前新增日志

- `coordinate relocalization requested`：诊断信号累计达到阈值，准备恢复。
- `coordinate relocalization forced`：导航控制器已消费请求，本帧暂停点击。
- `navigation forced global relocalization`：界面循环已调用导航核心强制全局重定位。
- `coordinate relocalization accepted`：全局模板匹配成功并被接受。
- `coordinate relocalization rejected`：强制重定位在超时时间内没有得到有效模板匹配。

## 设计约束

- 不使用固定全局偏移参数。
- 不修改绘图和定位的坐标体系。
- 重新匹配只解决“定位状态漂移/错配”，不能替代地图墙体、目标点和锚点设计问题。
- `wall_layer` 继续作为定位基准，`nav_wall_layer` 只给 A* 使用，不能混用。
