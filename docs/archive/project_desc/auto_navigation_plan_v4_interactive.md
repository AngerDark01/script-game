# 自动导航系统实施方案 (V4 - 交互式架构版)

## 1. 核心设计原则

本方案旨在取代 V3 方案，提供一个更健壮、更易于维护和扩展的实现蓝图。它遵循两大核心原则：

- **关注点分离 (Separation of Concerns)**: 将整个功能严格划分为三个独立的逻辑层，避免将所有代码都堆积在 `navigation_mode.py` 中。
    - **数据层 (`WaypointManager`)**: 负责航点数据的增、删、改、查、加载和保存。是唯一的数据源。
    - **算法层 (`WaypointNavigator`)**: 封装所有核心导航决策逻辑，如路径切入、滑动目标计算、APF调用等。它是一个无UI依赖的“导航大脑”。
    - **表现/集成层 (`NavigationModeWidget`)**: 现有的UI界面，作为“客户”调用算法层和数据层的服务，并负责响应用户输入和渲染最终结果。

- **交互式优先 (Interactive-First)**: 将航点的创建和编辑过程从一个离线的、手动的任务，转变为一个在线的、与UI深度融合的交互式功能，提升系统的整体可用性。

---

## 2. 原子化实施任务拆解

### 第一阶段：交互式航点创建与管理 (UI & 数据层)

**目标**: 构建一个允许用户在程序内通过点击地图来创建、修改、保存和加载航点路径的完整工作流。

**任务 1.1: [新] 创建功能目录与 `WaypointManager`**

- **动作**:
    1. 在 `core/` 目录下，创建一个新的子目录 `waypoint_navigation`。
    2. 在 `core/waypoint_navigation/` 中创建新文件 `waypoint_manager.py`。
- **目的**: 建立一个独立的模块来存放所有新功能代码，并首先实现数据管理核心。
- **`WaypointManager` 类设计 (`waypoint_manager.py`)**:
    - **属性**: `self.paths_data = {}`，用于在内存中缓存从文件加载的航点数据。
    - **加载/保存方法**:
        - `load_waypoints(self, map_folder: str) -> bool`: 接收地图文件夹路径，读取 `waypoints.json` 并存入 `self.paths_data`。
        - `save_waypoints(self, map_folder: str, map_name: str)`: 将内存中对应地图的航点数据写入 `waypoints.json`。
    - **编辑接口 (供UI调用)**:
        - `add_waypoint(self, map_name: str, path_name: str, point: tuple)`: 向指定路径添加一个点。
        - `remove_last_waypoint(self, map_name: str, path_name: str)`: 移除路径的最后一个点（用于撤销）。
        - `clear_path(self, map_name: str, path_name: str)`: 清空整条路径。
    - **查询接口**:
        - `get_path(self, map_name: str, path_name: str = "main_path") -> list | None`: 获取路径的航点列表。

**任务 1.2: [新] 在UI中添加航点编辑控件**

- **位置**: `gui/modes/navigation_mode.py`
- **动作**:
    1. 在 `NavigationModeWidget` 的 `__init__` 中，初始化 `self.waypoint_manager = WaypointManager()`。
    2. 添加 `[编辑航点]`, `[保存航点]`, `[撤销]`, `[清空]` 等 `QPushButton` 按钮。
    3. 添加一个状态标志 `self.is_waypoint_edit_mode = False`，由 `[编辑航点]` 按钮控制。

**任务 1.3: [新] 实现点击地图创建与实时渲染**

- **位置**: `gui/modes/navigation_mode.py`
- **动作**:
    1. 响应 `scalable_map` 控件的鼠标点击事件。在事件处理器中，检查 `if self.is_waypoint_edit_mode:`。
    2. 若为真，则获取地图坐标并调用 `self.waypoint_manager.add_waypoint(...)`。
    3. 创建一个 `_render_waypoints()` 方法，该方法从 `waypoint_manager` 获取最新路径数据，并使用 `QGraphicsPathItem` 和 `QGraphicsEllipseItem` 在地图上绘制路径和节点。
    4. 在所有编辑操作（增、删、清空、加载）后，调用 `_render_waypoints()` 刷新视图。

---

### 第二阶段：独立导航引擎的构建 (算法层)

**目标**: 创建一个完全独立于UI的、可测试的导航算法核心。

**任务 2.1: [新] 创建 `apf.py` 算法工具箱**

- **文件**: `core/waypoint_navigation/apf.py`
- **目的**: 将纯数学计算函数独立出来。
- **函数**:
    - `project_on_segment(point, seg_start, seg_end)`: 计算点到线段的投影。
    - `calculate_apf_vector(grid, player_pos, target_pos, scan_radius)`: 计算人工势场法的合力向量。

**任务 2.2: [新] 实现 `WaypointNavigator` 核心**

- **文件**: `core/waypoint_navigation/navigator.py`
- **目的**: 封装所有导航状态和决策逻辑，作为导航“大脑”。
- **`WaypointNavigator` 类设计**:
    - **属性**: `self.waypoints`, `self.current_waypoint_index`, `self.is_active`。
    - **方法 `start(self, player_pos: tuple, waypoints: list)`**: 接收玩家位置和航点列表，计算最近的切入点，设置 `self.current_waypoint_index`，并激活导航。
    - **方法 `stop(self)`**: 停用导航。
    - **方法 `update(self, player_pos: tuple, grid) -> tuple | None`**: 导航循环的核心。执行航点切换、计算“滑动目标点”、调用 `apf.calculate_apf_vector()`，并最终返回一个推荐的移动方向向量 `final_vec`。

---

### 第三阶段：无缝集成与UI改造 (集成层)

**目标**: 最小化地改动 `navigation_mode.py`，使其从“实干家”转变为“管理者”，仅负责调用和展现。

**任务 3.1: [修订] 改造 `navigation_mode.py`**

- **动作**:
    1. 在 `__init__` 中初始化 `self.waypoint_navigator = WaypointNavigator()`。
    2. **修改 `load_map`**: 调用 `self.waypoint_manager.load_waypoints()`。
    3. **修改 `toggle_navigation`**:
        - 开始时，从 `waypoint_manager` 获取路径，然后调用 `self.waypoint_navigator.start()`。
        - 停止时，调用 `self.waypoint_navigator.stop()`。
    4. **重构 `navigation_loop`**:
        - 移除所有旧的计算逻辑。
        - 新逻辑：获取 `player_pos` 和 `grid` -> 调用 `self.waypoint_navigator.update()` 得到 `final_vec` -> 如果 `final_vec` 有效，则执行移动 (`motion_controller`) 并更新UI箭头。

---

### 第四阶段：UI增强与可视化

**目标**: 为用户提供清晰的导航状态反馈。

**任务 4.1: [不变] 实现实时方向指示箭头**

- **位置**: `gui/modes/navigation_mode.py`
- **逻辑**:
    1. 创建一个箭头形状的 `QGraphicsPathItem`。
    2. 在 `navigation_loop` 中，使用 `waypoint_navigator.update()` 返回的 `final_vec` 来实时更新箭头的位置和旋转角度。
    3. 在 `toggle_navigation` 中控制箭头的显示与隐藏。
