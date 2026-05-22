# 自动导航系统实施方案 (V6 - 详细实现版)

## 1. 核心设计思想

(与V5版相同，强调导航策略、分层架构和交互式设计...)

---

## 2. 原子化实施任务拆解 (含实现思路)

### 第一阶段：交互式航点创建与管理 (UI & 数据层)

**任务 1.1: 创建功能目录与 `WaypointManager`**

- **动作**: 在 `core/` 下创建新目录 `waypoint_navigation`，并在其中创建 `waypoint_manager.py`。
- **实现思路**: 这个类是一个纯粹的数据管理器，不应包含任何UI或算法逻辑。

- **伪代码/示例 (`core/waypoint_navigation/waypoint_manager.py`)**:
  ```python
  import json
  import os

  class WaypointManager:
      """管理所有航点数据的加载、保存和编辑。"""
      def __init__(self):
          # 数据结构: {"map_name_1": {"main_path": [[x,y], ...]}, "map_name_2": ...}
          self.paths_data = {}

      def load_waypoints(self, map_folder: str) -> bool:
          """从指定地图文件夹加载 waypoints.json。"""
          filepath = os.path.join(map_folder, '''waypoints.json''')
          if not os.path.exists(filepath):
              self.paths_data = {}
              return False
          try:
              with open(filepath, '''r''') as f:
                  self.paths_data = json.load(f)
              return True
          except (json.JSONDecodeError, IOError):
              self.paths_data = {}
              return False

      def save_waypoints(self, map_folder: str) -> bool:
          """将内存中的航点数据保存到文件。"""
          filepath = os.path.join(map_folder, '''waypoints.json''')
          try:
              with open(filepath, '''w''') as f:
                  json.dump(self.paths_data, f, indent=2)
              return True
          except IOError:
              return False

      def add_waypoint(self, map_name: str, path_name: str, point: tuple):
          """向指定路径添加一个点。"""
          if map_name not in self.paths_data:
              self.paths_data[map_name] = {}
          if path_name not in self.paths_data[map_name]:
              self.paths_data[map_name][path_name] = []
          self.paths_data[map_name][path_name].append(list(point))

      def get_path(self, map_name: str, path_name: str = "main_path") -> list:
          """获取路径的航点列表。"""
          return self.paths_data.get(map_name, {}).get(path_name, [])

      # ... 其他编辑方法如 remove_last_waypoint, clear_path ...
  ```

**任务 1.2 & 1.3: UI控件与交互实现**

- **位置**: `gui/modes/navigation_mode.py`
- **实现思路**: 在UI的鼠标事件中增加模式判断，并调用 `WaypointManager`。渲染逻辑应独立成一个函数，在数据变更后调用以刷新视图。

- **伪代码/示例 (`gui/modes/navigation_mode.py`)**:
  ```python
  # in __init__
  self.waypoint_manager = WaypointManager()
  self.is_waypoint_edit_mode = False
  self.btn_edit_waypoints.clicked.connect(self.toggle_edit_mode)
  self.scalable_map.mouse_clicked.connect(self.on_map_clicked)

  def on_map_clicked(self, map_pos):
      if self.is_waypoint_edit_mode and self.current_map_name:
          self.waypoint_manager.add_waypoint(self.current_map_name, "main_path", map_pos)
          self._render_waypoints() # 数据变更后立即重绘

  def _render_waypoints(self):
      # 1. 清除旧的路径图形项
      if hasattr(self, '''waypoint_path_item'''):
          self.scene.removeItem(self.waypoint_path_item)

      # 2. 从manager获取最新路径数据
      path_points = self.waypoint_manager.get_path(self.current_map_name)
      if not path_points:
          return

      # 3. 创建并添加新的 QGraphicsPathItem
      path = QPainterPath()
      path.moveTo(path_points[0][0], path_points[0][1])
      for point in path_points[1:]:
          path.lineTo(point[0], point[1])
      
      self.waypoint_path_item = QGraphicsPathItem(path)
      self.waypoint_path_item.setPen(QPen(Qt.cyan, 2))
      self.scene.addItem(self.waypoint_path_item)
  ```

### 第二阶段：独立导航引擎的构建 (算法层)

**任务 2.1: 创建 `apf.py` 算法工具箱**

- **文件**: `core/waypoint_navigation/apf.py`
- **实现思路**: 包含纯粹的、无状态的数学计算函数。

- **伪代码/示例 (`core/waypoint_navigation/apf.py`)**:
  ```python
  import numpy as np

  def project_on_segment(point, seg_start, seg_end):
      # ... 实现向量投影的数学逻辑 ...
      # 返回投影点坐标
      pass

  def calculate_apf_vector(grid, player_pos, target_pos, scan_radius, repulsion_k, repulsion_range):
      # 1. 引力
      vec_attraction = np.array(target_pos) - np.array(player_pos)
      if np.linalg.norm(vec_attraction) > 0:
          vec_attraction = vec_attraction / np.linalg.norm(vec_attraction) # 归一化

      # 2. 斥力
      total_vec_repulsion = np.array([0.0, 0.0])
      px, py = int(player_pos[0]), int(player_pos[1])
      for r in range(max(0, py - scan_radius), min(grid.shape[0], py + scan_radius)):
          for c in range(max(0, px - scan_radius), min(grid.shape[1], px + scan_radius)):
              if grid[r, c] == 0: # 0代表障碍物
                  obstacle_pos = np.array([c, r])
                  dist_vec = np.array(player_pos) - obstacle_pos
                  dist = np.linalg.norm(dist_vec)
                  if 0 < dist < repulsion_range:
                      # 斥力大小与距离成反比
                      repulsion_force = repulsion_k * (1/dist - 1/repulsion_range) * (1/dist**2)
                      total_vec_repulsion += (dist_vec / dist) * repulsion_force
      
      # 3. 合力 (可加权)
      final_vector = vec_attraction + total_vec_repulsion
      if np.linalg.norm(final_vector) > 0:
          return final_vector / np.linalg.norm(final_vector)
      return np.array([0.0, 0.0])
  ```

**任务 2.2: 实现 `WaypointNavigator` 核心**

- **文件**: `core/waypoint_navigation/navigator.py`
- **实现思路**: 封装导航的状态和决策逻辑，但不做任何实际的移动或UI渲染。

- **伪代码/示例 (`core/waypoint_navigation/navigator.py`)**:
  ```python
  import numpy as np
  from . import apf

  class WaypointNavigator:
      def __init__(self):
          self.waypoints = []
          self.current_waypoint_index = 0
          self.is_active = False
          self.LOOKAHEAD_DISTANCE = 20.0 # “胡萝卜”距离
          self.WAYPOINT_THRESHOLD = 15.0 # 到达航点的判定距离

      def start(self, player_pos, waypoints):
          if not waypoints:
              self.is_active = False
              return
          self.waypoints = waypoints
          # 智能路径切入：找到最近的航点作为起点
          distances = [np.linalg.norm(np.array(player_pos) - np.array(wp)) for wp in self.waypoints]
          self.current_waypoint_index = np.argmin(distances)
          self.is_active = True

      def stop(self):
          self.is_active = False

      def update(self, player_pos, grid) -> np.ndarray | None:
          if not self.is_active:
              return None

          # 1. 航点切换逻辑
          current_target_waypoint = self.waypoints[self.current_waypoint_index]
          if np.linalg.norm(np.array(player_pos) - np.array(current_target_waypoint)) < self.WAYPOINT_THRESHOLD:
              if self.current_waypoint_index < len(self.waypoints) - 1:
                  self.current_waypoint_index += 1
              else:
                  self.stop() # 到达最终目的地
                  return None

          # 2. 计算滑动目标点
          # 简化处理：当前路径段的起点是上一个航点
          seg_start = self.waypoints[self.current_waypoint_index - 1] if self.current_waypoint_index > 0 else player_pos
          seg_end = self.waypoints[self.current_waypoint_index]
          
          # (此处调用 apf.project_on_segment 逻辑)
          # p_proj = apf.project_on_segment(...) 
          # sliding_target = p_proj + ...
          # 为简化，我们先直接使用下一个航点作为目标
          sliding_target = seg_end

          # 3. 调用APF计算最终方向
          final_vec = apf.calculate_apf_vector(grid, player_pos, sliding_target, ...)
          return final_vec
  ```

### 第三阶段：无缝集成与UI改造 (集成层)

**任务 3.1: 改造 `navigation_mode.py`**

- **实现思路**: 将 `navigation_loop` 的职责极大简化，只保留“获取输入 -> 调用大脑 -> 执行动作”的流程。

- **伪代码/示例 (`gui/modes/navigation_mode.py` 的 `navigation_loop`)**:
  ```python
  def navigation_loop(self):
      if not self.waypoint_navigator.is_active:
          self.nav_timer.stop()
          return

      # 1. 获取输入 (玩家位置和地图)
      player_pos = self.nav_core.localize(...)
      grid = self.nav_core.get_walkable_grid()
      if player_pos is None:
          return

      # 2. 调用大脑 (Navigator) 进行决策
      final_vec = self.waypoint_navigator.update(player_pos, grid)

      # 3. 执行动作 (移动和UI更新)
      if final_vec is not None and np.linalg.norm(final_vec) > 0:
          # a. 更新方向指示箭头 (任务4.1)
          self.update_direction_arrow(player_pos, final_vec)

          # b. 计算子目标并驱动 motion_controller
          sub_goal = np.array(player_pos) + final_vec * 30 # 乘以一个系数作为点击距离
          self.motion_controller.move_to_map_target(player_pos, sub_goal)
      else:
          # 导航可能已结束，隐藏箭头
          self.direction_arrow_item.setVisible(False)
  ```

### 第四阶段：UI增强与可视化

**任务 4.1: 实现实时方向指示箭头**

- **实现思路**: 在 `navigation_loop` 中根据 `final_vec` 更新一个 `QGraphicsItem` 的旋转角度。

- **伪代码/示例 (`gui/modes/navigation_mode.py`)**:
  ```python
  import math

  # in __init__ or _render_map
  # self.direction_arrow_item = QGraphicsPathItem(...) # 创建箭头形状

  def update_direction_arrow(self, player_pos, final_vec):
      self.direction_arrow_item.setPos(player_pos[0], player_pos[1])
      angle_rad = math.atan2(final_vec[1], final_vec[0])
      angle_deg = math.degrees(angle_rad)
      self.direction_arrow_item.setRotation(angle_deg)
      self.direction_arrow_item.setVisible(True)
  ```
