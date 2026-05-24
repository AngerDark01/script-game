
import cv2
import numpy as np
import heapq

class PathFinder:
    """
    A* 寻路算法实现
    针对大地图进行优化：使用降采样网格进行寻路
    """
    
    def __init__(
        self,
        downsample_factor=10,
        safety_margin=0,
        wall_shrink_iterations=0,
        start_clear_radius=30,
        walkable_snap_radius=18,
    ):
        """
        初始化
        
        Args:
            downsample_factor: 降采样因子（越大越快，但精度越低）
                               6000x6000地图，因子10 -> 600x600网格
        """
        self.downsample_factor = downsample_factor
        
        # 寻路参数
        self.safety_margin = max(0, int(safety_margin))  # 安全边距（像素，原始尺度）
        self.wall_shrink_iterations = max(0, int(wall_shrink_iterations))
        self.start_clear_radius = max(0, int(start_clear_radius))
        self.walkable_snap_radius = max(0, int(walkable_snap_radius))
    
    def find_path(self, wall_map, start_pos, end_pos, explored_map=None):
        """
        寻找路径
        
        Args:
            wall_map: 墙壁二值图 (0=空地, 255=墙)
            explored_map: 已探索区域图。传入时，0 会被视为不可走区域。
            start_pos: 起点 (x, y) 全局坐标
            end_pos: 终点 (x, y) 全局坐标
            
        Returns:
            list of (x, y): 路径点列表（全局坐标），如果无解返回None
        """
        h, w = wall_map.shape
        
        # 1. 坐标转换（全局 -> 网格）
        f = self.downsample_factor
        start_grid = (int(start_pos[0] / f), int(start_pos[1] / f))
        end_grid = (int(end_pos[0] / f), int(end_pos[1] / f))
        
        # 检查边界
        grid_h, grid_w = h // f, w // f
        if not (0 <= start_grid[0] < grid_w and 0 <= start_grid[1] < grid_h):
            print(f"[PathFinder] 起点超出边界: {start_grid}")
            return None
        if not (0 <= end_grid[0] < grid_w and 0 <= end_grid[1] < grid_h):
            print(f"[PathFinder] 终点超出边界: {end_grid}")
            return None
            
        # 2. 地图预处理（先让墙体变薄，再降采样）
        obstacle_map = self._build_obstacle_map(wall_map, grid_w, grid_h, explored_map=explored_map)
        obstacle_map = self._clear_start_area(obstacle_map, start_grid)
        
        # 检查起点和终点是否在障碍物内
        # 如果起点在墙内（可能是误差），尝试找最近的空地
        if obstacle_map[start_grid[1], start_grid[0]] > 0:
            print("[PathFinder] 起点在障碍物内，尝试寻找最近点...")
            start_grid = self._find_nearest_walkable(obstacle_map, start_grid)
            if start_grid is None:
                print("[PathFinder] 无法找到起点附近的空地")
                return None
                
        if obstacle_map[end_grid[1], end_grid[0]] > 0:
            print("[PathFinder] 终点在障碍物内，尝试寻找最近点...")
            end_grid = self._find_nearest_walkable(obstacle_map, end_grid)
            if end_grid is None:
                print("[PathFinder] 无法找到终点附近的空地")
                return None
        
        # 3. A* 算法
        path_grid = self._astar(obstacle_map, start_grid, end_grid)
        
        if path_grid is None:
            return None
            
        # 4. 坐标还原（网格 -> 全局）
        # 还原并进行平滑处理
        path_global = []
        for px, py in path_grid:
            path_global.append((int(px * f + f/2), int(py * f + f/2)))
            
        # 添加精确的终点
        if path_global[-1] != end_pos:
            path_global.append(end_pos)
            
        return path_global

    def _build_obstacle_map(self, wall_map, grid_w, grid_h, explored_map=None):
        """Build the downsampled obstacle grid used by A*."""
        source = wall_map
        if source.dtype != np.uint8:
            source = source.astype(np.uint8)

        _, binary_source = cv2.threshold(source, 50, 255, cv2.THRESH_BINARY)
        if self.wall_shrink_iterations > 0:
            # The stitched wall layer is often thicker than the game's true blocker.
            # Eroding wall pixels before planning keeps narrow routes open.
            thin_kernel = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
            binary_source = cv2.erode(
                binary_source,
                thin_kernel,
                iterations=self.wall_shrink_iterations,
            )

        small_map = cv2.resize(binary_source, (grid_w, grid_h), interpolation=cv2.INTER_AREA)
        _, binary_map = cv2.threshold(small_map, 50, 255, cv2.THRESH_BINARY)
        if explored_map is not None:
            known_source = explored_map
            if known_source.dtype != np.uint8:
                known_source = known_source.astype(np.uint8)
            _, known_source = cv2.threshold(known_source, 1, 255, cv2.THRESH_BINARY)
            known_small = cv2.resize(known_source, (grid_w, grid_h), interpolation=cv2.INTER_AREA)
            _, known_map = cv2.threshold(known_small, 1, 255, cv2.THRESH_BINARY)
            unknown_obstacle = np.where(known_map > 0, 0, 255).astype(np.uint8)
            binary_map = np.maximum(binary_map, unknown_obstacle)

        if self.safety_margin <= 0:
            return binary_map

        grid_margin = int(round(self.safety_margin / max(1, self.downsample_factor)))
        if grid_margin <= 0:
            return binary_map

        kernel_size = grid_margin * 2 + 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        return cv2.dilate(binary_map, kernel)

    def _clear_start_area(self, obstacle_map, start_grid):
        """Forgive local wall noise around the live player position."""
        radius = int(round(self.start_clear_radius / max(1, self.downsample_factor)))
        if radius <= 0:
            return obstacle_map

        cleared = obstacle_map.copy()
        h, w = cleared.shape
        cx, cy = int(start_grid[0]), int(start_grid[1])
        x1 = max(0, cx - radius)
        y1 = max(0, cy - radius)
        x2 = min(w, cx + radius + 1)
        y2 = min(h, cy + radius + 1)
        if x1 >= x2 or y1 >= y2:
            return cleared

        local = cleared[y1:y2, x1:x2]
        mask = np.zeros_like(local, dtype=np.uint8)
        cv2.circle(mask, (cx - x1, cy - y1), radius, 255, -1)
        local[mask > 0] = 0
        return cleared
        
    def _astar(self, grid, start, end):
        """A* 算法实现"""
        h, w = grid.shape
        
        open_set = []
        heapq.heappush(open_set, (0, start))
        
        came_from = {}
        g_score = {start: 0}
        f_score = {start: self._heuristic(start, end)}
        
        while open_set:
            current = heapq.heappop(open_set)[1]
            
            if current == end:
                return self._reconstruct_path(came_from, current)
            
            # 8方向移动
            neighbors = [
                (0, 1), (0, -1), (1, 0), (-1, 0),
                (1, 1), (1, -1), (-1, 1), (-1, -1)
            ]
            
            for dx, dy in neighbors:
                neighbor = (current[0] + dx, current[1] + dy)
                
                # 边界检查
                if not (0 <= neighbor[0] < w and 0 <= neighbor[1] < h):
                    continue
                
                # 障碍物检查 (0是空地, 255是墙)
                if grid[neighbor[1], neighbor[0]] > 0:
                    continue

                # 禁止斜向穿角：如果左右/上下相邻格有任一障碍，
                # 就不能从角点之间斜着挤过去。
                if dx != 0 and dy != 0:
                    side_a = (current[0] + dx, current[1])
                    side_b = (current[0], current[1] + dy)
                    if (
                        grid[side_a[1], side_a[0]] > 0
                        or grid[side_b[1], side_b[0]] > 0
                    ):
                        continue
                
                # 移动代价 (斜向移动代价更高)
                move_cost = 1.414 if dx != 0 and dy != 0 else 1.0
                tentative_g_score = g_score[current] + move_cost
                
                if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g_score
                    f_score[neighbor] = tentative_g_score + self._heuristic(neighbor, end)
                    heapq.heappush(open_set, (f_score[neighbor], neighbor))
                    
        return None  # 无路径
        
    def _heuristic(self, a, b):
        """曼哈顿距离启发式"""
        return abs(a[0] - b[0]) + abs(a[1] - b[1])
        
    def _reconstruct_path(self, came_from, current):
        """重建路径"""
        total_path = [current]
        while current in came_from:
            current = came_from[current]
            total_path.append(current)
        return total_path[::-1]  # 反转列表
        
    def _find_nearest_walkable(self, grid, pos, max_radius=None):
        """在给定半径内寻找最近的空地"""
        h, w = grid.shape
        cx, cy = pos
        if max_radius is None:
            max_radius = max(
                1,
                int(round(self.walkable_snap_radius / max(1, self.downsample_factor))),
            )
        
        for r in range(1, max_radius + 1):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if abs(dx) + abs(dy) > r: # 简单的曼哈顿半径近似
                        continue
                        
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < w and 0 <= ny < h:
                        if grid[ny, nx] == 0:
                            return (nx, ny)
        return None
