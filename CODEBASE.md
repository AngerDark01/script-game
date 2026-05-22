# CODEBASE

## 1. 项目概览
PySide6 + OpenCV 的实时小地图拼接与导航工具。绘图模式从游戏小地图截图提取 HSV/墙体特征并写入 `map_data/<name>/map_data.npz`；导航模式读取同一份地图数据、用实时截图定位玩家全局地图坐标，并可基于用户设置的出口、必经点、途经点执行自动导航。当前任务相关的关键约束是：定位截图范围、地图全局坐标、真实主画面点击范围必须分离，不能用旧偏移参数修正定位。

## 2. 目录结构图
```text
main.py - 创建 QApplication 和 MainWindow。
gui/app_context.py - 初始化共享服务：ScreenCapture、MapStitcher、PlayerTracker、PathFinder。
gui/main_window.py - 创建绘图/导航两个模式并共享 AppContext。
gui/navigation_params.py - 定义 NavConfig、RecognizerParams、NavPreferences，并负责 config.json 序列化契约。
gui/dialogs/nav_params_dialog.py - 导航参数 UI，使用 widget_map 将控件变化写回 NavConfig。
gui/modes/navigation_mode.py - 导航模式主 UI、地图加载、定位循环、路线编辑、自动导航和范围框显示。
gui/modes/mapping_widget.py - 绘图模式，保存 map_data.npz 和地图 config.json。
core/navigation_core.py - 导航定位核心，将实时小地图截图匹配到全局地图坐标。
core/stitcher_core.py - 建图拼接核心，维护 wall_layer/explored_map/current_pos。
core/pathfinder.py - A* 寻路，输入输出地图全局坐标。
core/path_utils.py - 路径平滑、投影、插值、出口区域判断工具。
core/auto_navigator.py - 自动导航状态机，输出路径子目标和是否应点击。
core/motion_controller.py - 将地图方向转换成真实屏幕鼠标点击。
tests/test_auto_navigator.py - 自动导航状态机行为测试。
tests/test_motion_controller.py - 点击半径夹紧逻辑测试。
```

## 3. 架构全景
```text
Level 1
┌──────────────┐       ┌──────────────────────────┐       ┌──────────────┐
│ Game screen  │ ───▶  │ Minimap Stitcher/Nav App │ ───▶  │ Mouse click  │
└──────────────┘       └──────────────────────────┘       └──────────────┘
```

```text
Level 2
┌──────────────┐
│ MainWindow   │
└──────┬───────┘
       ├──▶ MappingWidget ──▶ MapStitcher ──▶ map_data.npz/config.json
       └──▶ NavigationModeWidget ──▶ NavigationCore ──▶ global player pos
                                  └──▶ AutoNavigator ──▶ map subgoal
                                  └──▶ MotionController ──▶ Win32 mouse_event click
```

```text
Level 3: navigation click path
┌──────────────────────┐
│ navigation_loop      │
│ capture minimap      │
│ localize player      │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ AutoNavigator.update │
│ map pos -> path      │
│ path -> subgoal      │
└──────────┬───────────┘
           ▼ issued_click=True
┌────────────────────────────┐
│ MotionController           │
│ normalize map direction    │
│ clamp screen click radius  │
└──────────┬─────────────────┘
           ▼
┌──────────────────────┐
│ Win32 mouse_event    │
└──────────────────────┘
```

## 4. 模块与文件详解
### `gui/navigation_params.py`
职责：定义导航配置数据模型，并把地图 `config.json` 转换为运行时 `NavConfig`。
关键导出：`NavConfig`、`RecognizerParams`、`NavPreferences`、`_parse_hsv_list`。
对外依赖：无内部模块依赖。
注意事项：`monitor_size`/`draw_scale` 服务定位一致性；`game_view_map_size` 和点击半径参数服务主画面移动控制，不能反向影响定位。

### `core/motion_controller.py`
职责：把 `AutoNavigator` 给出的地图全局子目标转换为屏幕物理坐标点击。
关键导出：`MotionController`。
对外依赖：`core.input_driver.InputDriver`；`pydirectinput.click` 仅为异常兜底。
注意事项：当前不负责寻路、不负责定位，只处理“地图方向 -> 屏幕点击”。`movement_scale_factor` 先得到原始屏幕半径，再由 `movement_min_click_radius`/`movement_max_click_radius` 夹紧；底部 UI 防误点由 `bottom_click_guard_pixels` 在最终点击前单独处理，不反向修改移动比例。

### `gui/modes/navigation_mode.py`
职责：导航模式 UI 与运行循环，包含地图加载、定位、路线编辑、自动导航动作消费、绿色定位框和橙色真实可见框绘制。
关键导出：`NavigationModeWidget`。
对外依赖：`NavigationCore`、`MotionController`、`AutoNavigator`、`RouteManager`。
注意事项：绿色框来自 `capture_rect * draw_scale`，表示小地图截图定位范围；橙色框来自 `game_view_map_size`，表示主游戏画面真实可见/可交互范围。路线编辑分为两类点：`guide_points` 构成可被 A* 逐段追踪的路线骨架，`required_points` 是必须按顺序完成的阶段门，状态机按路线进度判断当前应追普通点还是必经点，并通过 `target_kind` 控制覆盖层只高亮真正当前目标。

### `core/route_manager.py`
职责：维护每张地图的 `route.json`，持久化出口、必经点、途经点。
关键导出：`RouteManager`。
对外依赖：标准库 `json`、`pathlib.Path`。
注意事项：`required_points` 和 `guide_points` 是两套独立序列；`clear_route()` 会同时清空两类点，避免旧路线状态残留。

### `core/auto_navigator.py`
职责：自动导航状态机，等待稳定定位、规划当前段路径、选择路径前方子目标、控制点击冷却和卡住恢复。
关键导出：`AutoNavigator`。
对外依赖：`core.path_utils`。
注意事项：输出的是地图全局坐标的 `target_pos/subgoal`，不应掺入屏幕点击半径。阶段 1 默认规划优先：`PathFinder` 使用变薄后的墙图，A* 失败时才进入局部脱困 fallback。`guide_points + exit` 始终是路线接入和行走骨架；`required_points` 不直接替代路线骨架，而是按其投影到路线骨架上的进度成为阶段门，接近当前必经点后才推进 `required_index`。

### `core/navigation_core.py`
职责：读取 `map_data.npz`，用实时小地图截图定位玩家在全局地图中的坐标。
关键导出：`NavigationCore`。
对外依赖：`HSVRecognizer`。
注意事项：`draw_scale` 必须与建图保持一致；输出坐标是全局地图坐标，不是屏幕点击坐标。`fog_layer` 仍会随地图包保存，但当前显示默认只渲染 `explored_map`（灰）和 `wall_layer`（白），不额外铺蓝底。战斗/事件场景下，F2F 跟踪优先使用 `wall_mask` 而不是混合 `match_mask`，以降低动态边缘特效带来的漂移。

### `core/pathfinder.py`
职责：对 `wall_layer` 先做墙体变薄，并结合 `explored_map` 排除未知区域，再降采样运行 A*，输出全局地图路径点。
关键导出：`PathFinder`。
对外依赖：无内部模块依赖。
注意事项：路径点用于地图导航，不能直接当屏幕点击点。默认 `safety_margin=0`、`wall_shrink_iterations=1`，优先避免缝隙/窄路被建图墙体误封；`explored_map==0` 必须视为不可走，否则 A* 会穿过地图外黑区。

### `core/stitcher_core.py`
职责：将实时小地图墙层/地面层融合到全局地图，并输出供绘图模式与导航模式共用的地图包。
关键导出：`MapStitcher`。
对外依赖：`cv2`、`numpy`。
注意事项：当前版本不再把整块截图矩形无脑写入 `explored_map`；优先使用 `fog_mask` 作为精准可见区域，并同步维护 `fog_layer`，这样生成的地图更接近游戏实际小地图结构。

## 5. 函数索引与算法实现
### `MotionController._calculate_target_screen_position(self, player_global_pos: tuple, target_global_pos: tuple) -> tuple[int, int] | None`
行为：把地图全局方向映射到人物屏幕中心附近的真实点击点。
算法：
1. 计算 `delta_map = target_global_pos - player_global_pos`。
2. 用 `math.hypot` 得到地图距离；若距离接近 0，记录 `last_click_info` 并返回 `None`。
3. 计算 `raw_screen_radius = map_distance * movement_scale_factor`。
4. 将半径夹到 `[movement_min_click_radius, movement_max_click_radius]`。
5. 将地图方向归一化为单位向量。
6. 屏幕点击点等于 `game_screen_center + direction * screen_radius`。
7. 记录 `last_click_info`，包含 map_delta、raw_screen_radius、screen_radius、direction、screen_pos。
副作用：更新 `self.last_click_info`。
失败行为：目标距离为 0 时不返回点击点。
调用关系：called by `MotionController.move_to_map_target()`；间接 called by `NavigationModeWidget.navigation_loop()`。

### `MotionController._apply_bottom_click_guard(self, screen_pos: tuple[int, int], driver=None)`
行为：防止自动导航点击落入游戏底部 UI 区域。
算法：
1. 若 `bottom_click_guard_pixels <= 0` 或未校准 `game_screen_center`，直接返回原点击点。
2. 从 `InputDriver.screen_height` 或 `pydirectinput.size()` 获取屏幕高度。
3. 计算禁点区顶部 `forbidden_top = screen_height - bottom_click_guard_pixels`，安全线 `safe_y = forbidden_top - bottom_click_guard_margin`。
4. 若目标 `y <= safe_y`，不调整。
5. 若目标在人物中心下方且超过安全线，沿 `game_screen_center -> screen_pos` 线段按比例缩短到 `safe_y`。
6. 返回调整后的点击点和 `bottom_guard` 诊断信息。
副作用：无直接鼠标副作用；调用方把结果写入 `last_click_info`。
失败行为：无法获取屏幕高度时保持原点并记录 `reason=no_screen_height`。
调用关系：called by `MotionController._execute_click()`。

### `NavigationModeWidget._update_game_view_rect(self, player_pos)`
行为：在地图视图中绘制橙色真实主画面范围框。
算法：
1. 校验 `game_view_rect_item`、`player_pos`、`nav_core`、`nav_config` 是否存在。
2. 读取 `nav_config.game_view_map_size`，小于等于 0 时隐藏橙色框。
3. 用 `nav_core.crop_offset` 将全局地图坐标转换为当前场景坐标。
4. 以玩家位置为中心，绘制边长为 `game_view_map_size` 的正方形。
副作用：更新 QGraphicsRectItem。
调用关系：called by `NavigationModeWidget.navigation_loop()`。

### `NavigationModeWidget._refresh_game_view_rect_from_known_position(self)`
行为：参数变化或保存后，在没有等待下一帧导航循环的情况下刷新橙色真实可见框。
算法：
1. 校验 `nav_core` 是否存在。
2. 按优先级选择 `nav_core.current_pos`、`nav_core.last_good_pos`、`nav_core.drawing_saved_pos`。
3. 找到可用位置后调用 `_update_game_view_rect()`。
副作用：立即更新 QGraphicsRectItem。
调用关系：called by `_on_parameter_changed()` and `_save_nav_config()`。

### `NavParametersDialog._auto_estimate_click_radius(self)`
行为：根据已校准的角色屏幕中心和物理屏幕边界估算点击半径，避免 2K 屏幕下半径配置过小。
算法：
1. 校验当前 `NavConfig` 和 `game_screen_center`。
2. 调用 `_screen_physical_bounds_for_center()` 找到包含该中心点的屏幕物理边界。
3. 计算中心点到屏幕四边的最小距离 `safe_radius`。
4. 取 `max_radius = clamp(safe_radius * 0.70, lower=180, upper=900)`。
5. 取 `min_radius = max(120, max_radius * 0.55)`。
6. 写入最小/最大点击半径控件，触发配置变更信号。
副作用：更新参数面板控件和 `nav_status_label`。
调用关系：called by `nav_auto_click_radius_btn.clicked`。

### `AutoNavigator.update(self, localized_pos, confidence: float, wall_map, pathfinder, now_ms: int, lookahead_distance=None)`
行为：消费当前定位结果，输出状态或移动动作。
算法：
1. 若暂停或未启动，返回状态。
2. 用 `observe_localization()` 过滤低置信度和异常跳变。
3. ACQUIRE/SHORT_LOST 状态需要稳定窗口满足后才规划。
4. PLAN_SEGMENT 先调用 `_align_route_to_current_position()` 将 `guide_index` 接入到当前位置附近，但不会越过当前必经点在路线骨架上的进度。
5. `_select_segment_target()` 比较当前普通点进度和当前必经点投影进度：普通点仍在必经点之前时追普通点；必经点已到达或位于当前普通点之前时追必经点；两类点都完成后追出口。
6. 默认调用 `PathFinder.find_path()` 用变薄墙图和已探索区域规划当前段路径；若显式 `prefer_direct_guidance=True` 才强制直线段。
7. 如果 A* 因墙体/障碍失败，不再构造到 `segment_target` 的长直线路径，而是用 `_set_local_fallback_path()` 生成当前人物附近、朝目标方向的一小段临时脱困点。
8. FOLLOW_SEGMENT 状态把当前位置投影到路径并选择 lookahead 子目标。
9. `click_cooldown_ms` 和 `min_click_target_delta` 满足时返回 `{"type": "move", "issued_click": True, "target_pos": subgoal}`。
10. 如果临时脱困点到达或无进展，进入 PLAN_SEGMENT 重新跑 A*；卡住时进入 STUCK_RECOVER，先做小幅左右绕障试探，再按冷却重规划或失败。
副作用：更新状态机、平滑控制位置、点击冷却时间。
调用关系：called by `NavigationModeWidget.navigation_loop()`。

### `AutoNavigator._set_local_fallback_path(self, target)`
行为：A* 失败时生成局部脱困路径，而不是直接点击下一目标点。
算法：
1. 调用 `_local_probe_towards_target()`，以当前人物位置为起点、当前段目标为方向参考。
2. `direct_fallback_distance` 限制前进距离，默认约 96 地图像素。
3. `direct_fallback_side_distance` 和 `direct_fallback_attempts` 在重复失败时轻微左右偏移。
4. 将 `current_path` 设置为 `[control_pos, probe]`。
5. 标记 `current_path_kind="local_fallback"`，让 `_follow_segment()` 到达临时点后重新规划而不是推进路线段。
副作用：更新 `current_path/current_path_kind/direct_fallback_attempts`。
调用关系：called by `AutoNavigator._plan_segment()`。

### `AutoNavigator._align_route_to_current_position(self)`
行为：自动导航启动或重定位后，根据当前位置选择应该追踪的路线标记。
算法：
1. 如果本轮已经对齐或没有当前位置，直接返回。
2. 读取 `guide_points + exit_region.center` 作为有序标记点。
3. 如果仍有未完成 `required_points`，计算当前必经点投影到路线骨架上的进度，后续接入候选不能超过该进度之后的第一个普通点。
4. 计算当前位置到每个标记点的距离，得到最近标记候选。
5. 调用 `_candidate_index_from_nearest_route_segment()`；若当前位置贴近某条路线段，则候选改为该段的下一个标记，避免在两个标记之间回头追上一个点。
6. 如果距离最近标记小于 `arrival_radius * route_marker_arrival_factor`，认为该标记已到达，目标推进到下一个标记。
7. 将 `guide_index` 设置为候选标记索引，并清空当前路径，下一步重新 A* 到该标记。
副作用：更新 `guide_index/current_path/current_target/current_path_kind`。
调用关系：called by `AutoNavigator._plan_segment()`。

### `AutoNavigator._select_segment_target(self)`
行为：在普通路线骨架、当前必经点和出口之间选择本次 A* 应追踪的段目标。
算法：
1. 若没有有效路线，返回 `("none", None)`。
2. 读取当前 `guide_index` 对应的普通点和当前 `required_index` 对应的必经点。
3. 当普通点和必经点同时存在时，把必经点投影到 `guide_points + exit` 路线骨架，得到必经点路线进度；同时读取当前普通点的路线进度。
4. 如果必经点进度小于等于当前普通点进度，返回 `("required", required_point)`，表示阶段门已经到达当前路线位置，必须先完成。
5. 如果当前普通点仍在必经点之前，返回 `("guide", guide_point)`，继续沿人工路线骨架行走，避免直接拉直线去下一个必经点。
6. 若只剩必经点则返回必经点；若只剩普通点则返回普通点；两者都完成后返回出口中心。
副作用：无；调用方会把结果写入 `current_target/current_target_kind`。
调用关系：called by `current_segment_target()`、`current_segment_target_kind()`、`_plan_segment()`。

### `AutoNavigator._candidate_index_from_nearest_route_segment(self, points)`
行为：当当前位置在路线段附近时，按路线方向接入下一标记。
算法：
1. 遍历每一段 `points[i] -> points[i+1]`。
2. 将当前位置投影到线段，计算投影点和线段距离。
3. 选择距离最近且小于 `route_snap_max_distance` 的线段。
4. 如果投影参数 `t <= route_snap_segment_threshold`，候选仍是该段起点；否则候选是该段终点，即沿路线向出口方向推进。
副作用：无。
调用关系：called by `_align_route_to_current_position()`。

### `PathFinder._build_obstacle_map(self, wall_map, grid_w, grid_h)`
行为：把建图墙层转换为 A* 使用的低分辨率障碍图。
算法：
1. 将输入墙图转为 `uint8` 并阈值化。
2. 如果 `wall_shrink_iterations > 0`，用 `MORPH_CROSS` 腐蚀墙像素，让建图偏厚的墙体变薄。
3. 将变薄后的墙图 resize 到 A* 网格尺寸。
4. 再阈值化得到 `binary_map`。
5. 如果传入 `explored_map`，把已探索区域 resize 到同一网格，`explored_map==0` 的网格强制设为障碍。

### `PathFinder._astar(self, grid, start, end)`
行为：在低分辨率障碍图上执行 8 方向 A*。
算法：
1. 从 `start` 开始，用 `g_score + heuristic` 的最小堆扩展节点。
2. 邻居支持上下左右和四个对角方向。
3. 若目标邻居本身是障碍，直接跳过。
4. 若是对角移动，还要额外检查两侧正交相邻格；任一侧是障碍就禁止斜穿角，避免从墙角之间硬挤过去。
5. 使用直行 `1.0`、斜走 `1.414` 的代价累计，直到到达终点或无路可走。

### `MapStitcher._merge_frame_weighted(self, save_mask, fog_mask, h, w, px, py, force=False)`
行为：把当前帧的墙体层与地面/禁区候选层融合进全局地图。
算法：
1. 根据当前全局坐标和玩家在小地图中的相对位置，计算当前帧在画布上的 ROI。
2. 对墙体像素累积 `weight_layer`，权重大于阈值后再写入 `wall_layer`，避免单帧噪声污染地图。
3. 从 `fog_mask` 提取精准可见区域；像素数足够时，将其写入 `fog_layer` 并作为本帧 `explored_map` 的更新依据。
4. 只有当地面/迷雾提取几乎为空时，才回退到旧的“整块截图矩形” explored 逻辑，避免某些地图完全不出背景。
5. 强制把墙体也并入 `explored_map`，保证裁剪和导航不会把边界丢掉。

### `MapStitcher.get_enhanced_map(self, margin=500)`
行为：返回绘图模式显示用的彩色全局图。
算法：
1. 以 `explored_map`/`wall_layer` 的非零包围盒为基础自动裁剪。
2. `explored_map` 显示为灰色有效区域。
3. `fog_layer` 继续保存在地图包中，但默认不直接渲染到 UI。
4. `wall_layer` 显示为白色墙体并覆盖在最上层。

### `HSVRecognizer.extract_combined(self, img, player_pos=None)`
行为：提取用于拼接/导航的组合特征。
算法：
1. 先提取 `wall_mask`、`fog_mask` 和 `edges`。
2. 对高饱和度彩色区域生成 `dynamic_mask`，并做一次小核膨胀，把事件图标/彩色技能标记及其轮廓一起抹掉。
3. 将 `dynamic_mask` 同时从 `wall_mask`、`fog_mask`、`edges` 中剔除，避免动态图标污染静态地图特征。
4. 在人物中心周围再挖一个固定半径的圆形屏蔽区，压制玩家脚下和近身特效。
5. 最后才把 `wall_mask` 和 `edges` 融合成 `match_mask`，用于配准。
6. 如果 `safety_margin <= 0`，直接返回，不再默认膨胀墙体。
7. 如果显式设置安全边距，则按网格比例膨胀障碍图。
副作用：无。
调用关系：called by `PathFinder.find_path()`。

## 6. 完整数据流链路
### Flow: 自动导航移动点击
1. `NavigationModeWidget.navigation_loop()` 输入 `capture_rect`、屏幕截图帧；输出 `localized_pos=(global_x, global_y)`；副作用是更新地图上的玩家点、绿色定位框、橙色真实可见框。
2. `NavigationCore.localize()` 输入实时小地图截图和 `player_pos`；输出地图全局坐标和置信度；副作用是更新 `current_pos/last_good_pos/prev_mask`。
3. `AutoNavigator.update()` 输入地图全局坐标、置信度、`wall_layer`、`explored_map`、`PathFinder`；默认用变薄墙图和已探索区域做 A* 当前段规划，失败时才生成局部脱困点；输出 `auto_action`，其中 `target_pos` 是地图全局子目标。
4. `NavigationModeWidget.navigation_loop()` 检查 `auto_action.type == "move"` 且 `issued_click=True`；副作用是调用运动控制器。
5. `MotionController.move_to_map_target()` 输入玩家地图全局坐标和目标地图全局坐标；输出 `last_click_info`；副作用是调用 `_execute_click()`。
6. `MotionController._execute_click()` 输入屏幕物理坐标；先用 `_apply_bottom_click_guard()` 避免落入底部 UI，再通过 `InputDriver.click()` 执行 Win32 `SetCursorPos + mouse_event`，失败时才回退 `pydirectinput.click(x, y)`。

### Flow: 导航参数保存和加载
1. `NavigationModeWidget.load_map()` 读取 `map_data/<map>/config.json`。
2. `NavConfig.from_dict()` 将 dict 转为配置对象；缺失新字段时使用默认值。
3. `NavParametersDialog.set_config_to_ui()` 将配置同步到控件。
4. 控件变化触发 `_update_config_value()`，通过 `dataclasses.replace()` 创建新配置并发出 `parameters_changed`。
5. `NavigationModeWidget._on_parameter_changed()` 保存内存态配置，立即更新运动控制器参数，并通过 `_refresh_game_view_rect_from_known_position()` 重绘橙色框。
6. 同步调用 `AutoNavigator.configure()` 应用自动点击冷却和目标变化阈值。
7. 用户保存时 `_save_nav_config()` 调用 `NavConfig.to_dict()` 写回地图配置文件，并再次刷新橙色框。

### Flow: 点击半径诊断
1. `MotionController._calculate_target_screen_position()` 记录 `raw_screen_radius` 和夹紧后的 `screen_radius`。
2. `NavigationModeWidget.navigation_loop()` 在实际点击后追加显示 `click r:<screen_radius>/raw:<raw_screen_radius>`。
3. 如果 `raw` 明显大于 `r`，说明当前点击被 `movement_max_click_radius` 限制；如果 `raw` 和 `r` 都小，说明路径子目标距离或映射比例过小。

## 7. 外部集成详情
`main.py` Windows 启动前置条件：先设置 DPI awareness，再检测管理员权限；若不是管理员，则通过 `ShellExecuteW(..., "runas", sys.executable, ...)` 触发 UAC 重新启动当前脚本并退出原进程。真实游戏输入依赖管理员完整性级别。

`InputDriver.click(x, y)`：由 `MotionController._execute_click()` 的 `win32_mouse_event` 后端调用，执行 `SetCursorPos(x, y)` 后用 Win32 `mouse_event` 分开发送 left-down/left-up。该路径来自旧脚本 `t2.py` 的可用实现，当前是游戏点击主后端。

`pydirectinput.click(x, y)`：仍作为 `MotionController` 的异常兜底和诊断工具保留。失败风险包括游戏窗口未聚焦、坐标在窗口外、权限/输入钩子被游戏屏蔽。

## 8. 数据模型与契约
### `NavConfig`
字段：
`draw_scale: float` - 建图/定位地图缩放。
`monitor_logical_center: tuple[int, int] | None` - 小地图截图中心，服务定位。
`monitor_region: dict | None` - 拉框截图区域，服务定位。
`monitor_size: int` - 正方形截图边长，服务定位。
`fps: int` - 导航循环刷新率。
`game_screen_center: tuple[int, int] | None` - 主游戏画面人物屏幕中心，服务鼠标点击。
`movement_scale_factor: float` - 地图距离到原始屏幕点击半径的比例。
`game_view_map_size: int` - 橙色真实主画面可见/可交互框在地图坐标中的边长。
`movement_min_click_radius: int` - 屏幕点击最小半径，防止点在人物脚下。
`movement_max_click_radius: int` - 屏幕点击最大半径，防止点出真实可交互区域。
`auto_click_cooldown_ms: int` - 自动导航两次真实点击之间的最小间隔，默认 260ms。
`auto_min_click_target_delta: float` - 冷却结束后，子目标至少变化多少地图像素才重复点击，默认 8.0。
`bottom_click_guard_pixels: int` - 屏幕底部禁点区高度，默认 300px，设为 0 可关闭；只在点击落入底部 UI 时沿原方向缩短半径。

## 9. 风险与隐患登记
P1 - `MotionController._calculate_target_screen_position()` 默认半径未校准。触发条件：游戏实际点击触发距离大于 180px 或可交互范围小于 360px。复现方式：自动导航状态栏显示 `click r`，但人物不移动或点击到不可达点。建议：在参数面板调整最小/最大点击半径，并用橙色框观察真实可见范围。

P1 - `main.py` 的 UAC relaunch 会启动一个新的管理员进程并退出原进程。触发条件：从非管理员 shell/IDE 启动。复现方式：启动后弹出 UAC，授权后新窗口启动；如果用户取消授权，程序退出。建议：测试时确认控制台输出 `Admin: True`。

P2 - `NavigationModeWidget._render_route_overlay()` 在自动导航每帧清空并重绘路线层。触发条件：高 FPS 或长路径。复现方式：地图视图卡顿或闪烁。建议：后续按路径/subgoal 变化缓存绘制。

## 10. Input Control Current Notes
`core/input_driver.py` is part of the movement chain. It wraps Win32 `SetCursorPos`, `WindowFromPoint`, `SetForegroundWindow`, `GetForegroundWindow`, `GetClipCursor`, and `mouse_event`; `click()` performs separate down/up events with a short hold instead of a combined instant click.

`core/motion_controller.py` still owns only map-direction to screen-click conversion. The main project backend is `win32_mouse_event`: `MotionController._send_click()` calls `InputDriver.click(x, y, button="primary", hold_seconds=0.05, move_delay=0.02)`. `pydirectinput.click(x, y)` is only used as a fallback if the primary backend raises.

`core/auto_navigator.py` now defaults back to planning-first guidance. User-defined guide points and exit region still define major route intent, but each segment is planned with `PathFinder` on a thinned wall map constrained by `explored_map`. Direct full-segment guidance is retained only as explicit `prefer_direct_guidance=True`; A* failure uses a short local fallback probe near the player and then re-plans. Default automatic click cadence is `auto_click_cooldown_ms=260` and `auto_min_click_target_delta=8.0`, both exposed in the navigation parameter dialog.

`bottom_click_guard_pixels` protects the game's bottom UI/hotbar/chat region without changing the normal movement mapping. If a computed click lands below the safe line, `MotionController` projects that point back along the same center-to-target vector, effectively clicking slightly closer to the character in the same direction.

`gui/modes/navigation_mode.py::_set_game_input_window_mode()` prevents the PySide main window from intercepting auto-navigation clicks. While auto navigation is active, the main window is removed from `WindowStaysOnTopHint` and lowered; when auto navigation or navigation stops, the previous topmost state is restored. The transparent monitor overlay remains click-through and is not the expected click target.

### 2026-05-20 Correction
The stable movement baseline is the original `pydirectinput.click(x, y)` call. Do not replace it with `moveTo + mouseDown + mouseUp` unless it is separately verified in the target game environment. Window focusing is optional (`focus_before_click=False` by default) because it can interfere with the already-working cursor movement path.

`NavParametersDialog.set_config_to_ui()` now uses `QSignalBlocker` while writing widget values and `_connect_signals()` is one-shot. This avoids PySide `disconnect` RuntimeWarning messages during startup/config refresh.

### 2026-05-20 Click Diagnostics
`MotionController._execute_click()` logs the requested coordinate, final coordinate, whether clamping changed it, `pydirectinput.size()`, pydirectinput cursor position before/after, Win32 cursor position before/after, target window information, foreground window information, current `ClipCursor` rectangle, focus HWND, and confirmation-click state. This is intended to separate coordinate mapping failures from Unreal/Windows mouse capture or "click reached the wrong window" failures during real-game testing.

### 2026-05-20 Standalone Input Probe
`utils/input_probe.py` is a standalone manual probe for testing real game input before changing `MotionController`. It supports `pydi_click_xy`, `pydi_move_click`, `pydi_hold_xy`, `setcursor_pydi_click`, `setcursor_pydi_hold`, and `setcursor_win32_click`. It is diagnostic-only unless launched with `--execute`.

### 2026-05-20 DPI/Input Coordinate Finding
Runtime probe on the user's machine showed `pydirectinput.size() == (1707, 1067)`, `GetSystemMetrics(0/1) == (1707, 1067)`, and Qt `devicePixelRatio() == 1.5`. Therefore screenshot capture can still require physical coordinates, but `MotionController` should feed `pydirectinput` input coordinates consistently. `_clamp_screen_pos()` is now disabled by default; enabling it can still rewrite targets such as `(1987, 569)` or `(1559, 1469)` to screen-edge points, so it should only be used after the coordinate system is proven.
