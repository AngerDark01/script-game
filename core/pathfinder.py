
import cv2
import numpy as np
import heapq

class PathFinder:
    """
    A* 寻路算法实现
    针对大地图进行优化：使用降采样网格进行寻路
    """
    
    def __init__(self, downsample_factor=10):
        """
        初始化
        
        Args:
            downsample_factor: 降采样因子（越大越快，但精度越低）
                               6000x6000地图，因子10 -> 600x600网格
        """
        self.downsample_factor = downsample_factor
        
        # 寻路参数
        self.safety_margin = 5  # 安全边距（像素，原始尺度）
    
    def find_path(self, wall_map, start_pos, end_pos):
        """
        寻找路径
        
        Args:
            wall_map: 墙壁二值图 (0=空地, 255=墙)
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
            
        # 2. 地图预处理（降采样 + 膨胀）
        # 降采样
        small_map = cv2.resize(wall_map, (grid_w, grid_h), interpolation=cv2.INTER_AREA)
        
        # 二值化（确保墙壁清晰）
        _, binary_map = cv2.threshold(small_map, 50, 255, cv2.THRESH_BINARY)
        
        # 膨胀（增加安全距离）
        # 原始安全距离5px -> 网格安全距离 5/f (至少1)
        kernel_size = max(1, int(self.safety_margin / f)) * 2 + 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        obstacle_map = cv2.dilate(binary_map, kernel)
        
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
        
    def _find_nearest_walkable(self, grid, pos, max_radius=10):
        """在给定半径内寻找最近的空地"""
        h, w = grid.shape
        cx, cy = pos
        
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
