# 自动导航系统实施方案 (V3 - 最终版)

## 1. 核心思想

本方案旨在实现一个高容错、高效率、路径平滑的2D自动导航系统。它结合了 **人工预设航点** 的全局规划能力和 **人工势场法 (APF)** 的局部实时避障能力，并通过引入 **滑动目标点** 机制来确保导航的流畅性和前进方向的唯一性。

- **战略层 (离线设计)**: 由地图设计者为每张地图手动创建一条或多条关键路径，并保存为“航点 (Waypoints)”序列。这构成了AI导航的“高速公路网”。
- **战术层 (运行时)**:
    - **路径切入**: 导航启动时，系统自动计算玩家当前位置，并找到预设路径上最近的航点作为“切入点”，实现无缝、高容错的导航续行。
    - **局部导航**: 采用APF（人工势场法）作为“驾驶员”，负责在两个航点之间进行平滑、安全的移动。
    - **前进引导**: 引入“滑动目标点”机制，将APF的引力目标设置为路径上一个动态的、永远在玩家前方的“胡萝卜”，从根本上解决传统APF可能出现的“回头”和“抖动”问题。

## 2. 原子化实施任务拆解

### 第一阶段：航点数据的创建与加载 (一次性工作)

**任务 1.1: [人工] 定义并保存航点数据**

- **目标**: 为地图创建关键路径。
- **操作**:
    1. 通过临时脚本或修改UI的点击事件，录制路径上关键拐点的坐标。
    2. 将坐标序列保存为JSON文件。
- **产物**: 在地图文件夹下创建 `waypoints.json` 文件。
- **示例 (`map_data/asdf/waypoints.json`)**:
  ```json
  {
    "main_path": [
      [150, 400],
      [200, 350],
      [280, 320],
      [350, 250]
    ]
  }
  ```

**任务 1.2: 在 `navigation_mode.py` 中加载航点数据**

- **目标**: 在加载地图时，将对应的航点文件读入内存。
- **位置**: `gui/modes/navigation_mode.py` 的 `load_map` 方法。
- **步骤**:
    1. 在 `load_map` 中，成功加载地图后，检查并读取同目录下的 `waypoints.json`。
    2. 将解析后的路径数据存储到 `NavigationModeWidget` 的属性中（例如 `self.predefined_paths`）。

### 第二阶段：导航启动与路径切入 (运行时)

**任务 2.1: 实现智能路径切入逻辑**

- **目标**: 导航开始时，自动从预设路径上最合理的位置开始。
- **位置**: `gui/modes/navigation_mode.py` 的 `toggle_navigation` 方法。
- **步骤**:
    1. 在“开始导航”的逻辑块中，获取要使用的航点序列。
    2. 获取玩家当前位置 `player_pos`。
    3. **遍历航点序列**，找到距离 `player_pos` 最近的航点，将其索引记录为 `self.current_waypoint_index`。这确保了无论从哪里开始，都能无缝续行。

### 第三阶段：APF局部导航与“滑动目标”实现 (导航循环核心)

**任务 3.1: 在 `pathfinder.py` 中实现向量投影函数**

- **目标**: 创建一个计算点到线段投影的辅助函数，这是“滑动目标”机制的基础。
- **函数签名**: `project_on_segment(point, seg_start, seg_end)`。
- **逻辑**: 计算 `point` 在线段 `seg_start` -> `seg_end` 上的投影点坐标。

**任务 3.2: 在 `pathfinder.py` 中实现APF向量计算函数**

- **目标**: 根据引力和斥力，计算当前最佳移动方向。
- **函数签名**: `calculate_apf_vector(grid, player_pos, target_pos, scan_radius)`。
- **逻辑**:
    1. **引力**: `vec_attraction = target_pos - player_pos`。
    2. **斥力**: 扫描 `player_pos` 周围 `scan_radius` 范围内的 `grid`（二值化地图），对所有障碍物点计算斥力向量并求和。
    3. 返回合力向量 `final_vector = vec_attraction + total_vec_repulsion`。

**任务 3.3: 改造 `navigation_loop` 以实现“滑动目标”驱动**

- **目标**: 将所有模块串联，实现最终的、平滑的导航逻辑。
- **位置**: `gui/modes/navigation_mode.py` 内的 `navigation_loop` 方法。
- **核心步骤**:
    1. 获取玩家当前位置 `player_pos`。
    2. **航点切换**: 判断是否到达当前路径段的终点，如果到达，则将目标切换到下一个路径段 (`self.current_waypoint_index += 1`)。
    3. **计算滑动目标**:
        a. 获取当前路径段的起点 `seg_start` 和终点 `seg_end`。
        b. 调用 `project_on_segment()` 计算玩家在路径段上的投影点 `p_proj`。
        c. 从 `p_proj` 沿路径方向向前延伸固定距离，得到“滑动目标点” `sliding_target`。
    4. **计算方向**: 调用 `calculate_apf_vector()`，传入 `player_pos` 和 `sliding_target`，得到最终方向向量 `final_vec`。
    5. **执行移动**:
        a. 根据 `final_vec` 计算出 `motion_controller` 需要的“子目标”坐标。
        b. 调用 `self.motion_controller.move_to_map_target()` 执行点击。

### 第四阶段：UI增强与可视化

**任务 4.1: 实现实时方向指示箭头**

- **目标**: 在UI上实时显示AI的导航意图。
- **位置**: `gui/modes/navigation_mode.py`。
- **步骤**:
    1. 在 `_render_map` 中创建一个箭头形状的 `QGraphicsPathItem` (`self.direction_arrow_item`)。
    2. 在 `navigation_loop` 中，根据计算出的 `final_vec`，实时更新箭头的位置（与玩家位置同步）和旋转角度。
    3. 在 `toggle_navigation` 中控制箭头的显示与隐藏。
