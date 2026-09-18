# 自动导航系统实施方案 (V5 - 最终版)

## 1. 核心设计思想

本方案旨在为项目构建一个健壮、高效、可维护且具备良好用户体验的2D自动导航系统。方案融合了V4的先进软件架构和V3的精细导航策略，遵循以下核心思想：

### 1.1. 导航策略：智能驾驶的艺术

我们模拟一个智能驾驶员的行为，将导航过程分解为战略和战术两个层面：

- **战略层 (离线设计)**: 由用户（地图设计师）通过交互式界面，为每张地图手动规划出一条或多条关键路径，并保存为“航点 (Waypoints)”序列。这构成了AI导航的“高速公路网”，是全局最优路径的体现。

- **战术层 (运行时)**:
    - **智能路径切入**: 导航启动时，系统自动计算玩家当前位置，并找到预设路径上最近的航点作为“切入点”，实现随时随地、无缝、高容错的导航续行。
    - **APF局部导航**: 采用APF（人工势场法）作为“驾驶员”，负责在两个航点之间进行平滑、安全的实时避障移动。它根据二值化的地图数据，精确地感知墙体（斥力）和目标（引力）。
    - **“滑动目标”前进引导**: 为从根本上解决传统APF可能出现的“回头”和“抖动”问题，我们引入“滑动目标点”机制。该机制将APF的引力目标设置为路径上一个动态的、永远在玩家前方的“胡萝卜”，确保导航方向的唯一性和路径的平滑过渡。

### 1.2. 软件架构：关注点分离 (Separation of Concerns)

为保证代码的清晰、可测试和可扩展性，我们将整个功能严格划分为三个独立的逻辑层：

- **数据层 (`WaypointManager`)**: 负责航点数据的增、删、改、查、加载和保存。是项目中关于航点路径的唯一真实数据源 (Single Source of Truth)。
- **算法层 (`WaypointNavigator`)**: 封装所有核心导航决策逻辑，如路径切入、滑动目标计算、APF调用等。它是一个不依赖任何UI的、纯粹的“导航大脑”。
- **表现/集成层 (`NavigationModeWidget`)**: 作为用户界面，它是算法和数据服务的“客户”，负责响应用户输入（如点击地图、按钮），调用后两层提供的服务，并渲染最终的导航路径、箭头等可视化结果。

### 1.3. 交互设计：交互式优先 (Interactive-First)

我们将航点的创建和编辑过程从一个离线的、手动的任务，转变为一个在线的、与UI深度融合的交互式功能，极大地提升了系统的整体可用性和地图路径的迭代效率。

---

## 2. 原子化实施任务拆解

### 第一阶段：交互式航点创建与管理 (UI & 数据层)

**目标**: 构建一个允许用户在程序内通过点击地图来创建、修改、保存和加载航点路径的完整工作流。

**任务 1.1: 创建功能目录与 `WaypointManager`**
- **动作**: 在 `core/` 下创建新目录 `waypoint_navigation`，并在其中创建 `waypoint_manager.py`。
- **`WaypointManager` 类设计**: 
    - **核心职责**: 管理所有航点数据的加载、缓和、修改与保存。
    - **接口**: 提供 `load_waypoints`, `save_waypoints`, `add_waypoint`, `remove_last_waypoint`, `get_path` 等清晰的方法供UI层调用。

**任务 1.2: 在UI中添加航点编辑控件**
- **位置**: `gui/modes/navigation_mode.py`
- **动作**: 添加 `[编辑航点]`, `[保存航点]`, `[撤销]` 等按钮，并引入 `self.is_waypoint_edit_mode` 状态标志来切换UI模式。

**任务 1.3: 实现点击地图创建与实时渲染**
- **位置**: `gui/modes/navigation_mode.py`
- **动作**: 响应地图的鼠标点击事件，在编辑模式下调用 `waypoint_manager` 添加航点，并创建一个 `_render_waypoints()` 方法，根据 `waypoint_manager` 的数据实时绘制路径和节点。

### 第二阶段：独立导航引擎的构建 (算法层)

**目标**: 创建一个完全独立于UI的、可测试的导航算法核心。

**任务 2.1: 创建 `apf.py` 算法工具箱**
- **文件**: `core/waypoint_navigation/apf.py`
- **目的**: 将纯数学计算函数独立出来，便于复用和测试。
- **核心函数**:
    - `project_on_segment(point, seg_start, seg_end)`: 计算点到线段的投影，是“滑动目标”机制的基础。
    - `calculate_apf_vector(grid, player_pos, target_pos, scan_radius)`: 实现APF算法。逻辑包含计算指向 `target_pos` 的**引力向量**，并扫描 `grid` 计算来自障碍物的**斥力向量**，最终返回两者的合力向量。

**任务 2.2: 实现 `WaypointNavigator` 核心**
- **文件**: `core/waypoint_navigation/navigator.py`
- **目的**: 封装所有导航状态和决策逻辑，作为导航“大脑”。
- **核心方法**:
    - `start(self, player_pos: tuple, waypoints: list)`: 接收玩家位置和航点列表，计算最近的切入点，设置初始 `current_waypoint_index`，并激活导航。
    - `stop(self)`: 停用导航。
    - `update(self, player_pos: tuple, grid) -> tuple | None`: **导航循环的核心**。此方法将执行完整的决策链条：
        1. 检查是否需要切换到下一个航点/路径段。
        2. 调用 `apf.project_on_segment()` 计算玩家在当前路径段上的投影。
        3. 根据投影点计算出前方的“滑动目标点”。
        4. 调用 `apf.calculate_apf_vector()` 计算出最终的前进方向向量 `final_vec`。
        5. 返回 `final_vec`。

### 第三阶段：无缝集成与UI改造 (集成层)

**目标**: 最小化地改动 `navigation_mode.py`，使其从“实干家”转变为“管理者”，仅负责调用和展现。

**任务 3.1: 改造 `navigation_mode.py`**
- **动作**: 
    1. 在 `__init__` 中初始化 `self.waypoint_manager` 和 `self.waypoint_navigator`。
    2. **修改 `load_map`**: 调用 `self.waypoint_manager.load_waypoints()` 并触发渲染。
    3. **修改 `toggle_navigation`**: 开始时，从 `waypoint_manager` 获取路径并调用 `waypoint_navigator.start()`；停止时，调用 `waypoint_navigator.stop()`。
    4. **重构 `navigation_loop`**: 移除所有旧计算逻辑。新的循环体变得极其简单：获取 `player_pos` -> 调用 `self.waypoint_navigator.update()` 得到 `final_vec` -> 如果 `final_vec` 有效，则驱动 `motion_controller` 并更新UI箭头。

### 第四阶段：UI增强与可视化

**目标**: 为用户提供清晰、直观的导航状态反馈。

**任务 4.1: 实现实时方向指示箭头**
- **位置**: `gui/modes/navigation_mode.py`
- **逻辑**: 
    1. 创建一个箭头形状的 `QGraphicsPathItem`。
    2. 在 `navigation_loop` 中，使用 `waypoint_navigator.update()` 返回的 `final_vec` 来实时更新箭头的位置（与玩家位置同步）和旋转角度。
    3. 在 `toggle_navigation` 中控制箭头的显示与隐藏。