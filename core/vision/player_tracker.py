"""
人物位置追踪器
从HSV mask中检测玩家位置
"""

import cv2
import numpy as np
from collections import deque


class PlayerTracker:
    """玩家位置追踪器"""
    
    def __init__(self, max_trail_length=200):
        """
        初始化
        
        Args:
            max_trail_length: 轨迹最大长度
        """
        self.last_position = None
        self.trail = deque(maxlen=max_trail_length)
        self.global_trail = deque(maxlen=max_trail_length)
    
    def detect_player(self, player_mask):
        """
        从mask中检测玩家位置
        
        Args:
            player_mask: 玩家层mask（二值化）
        
        Returns:
            (x, y): 玩家在小地图中的局部坐标，失败返回None
        """
        # 查找轮廓
        contours, _ = cv2.findContours(
            player_mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )
        
        if not contours:
            return self.last_position  # 返回上一次位置
        
        # 找到最大轮廓
        largest = max(contours, key=cv2.contourArea)
        
        # 面积太小，认为是噪点
        if cv2.contourArea(largest) < 10:
            return self.last_position
        
        # 计算质心
        M = cv2.moments(largest)
        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            
            self.last_position = (cx, cy)
            self.trail.append((cx, cy))
            
            return (cx, cy)
        
        return self.last_position
    
    def update_global_trail(self, player_global_pos):
        """
        更新全局坐标轨迹
        
        Args:
            player_global_pos: (global_x, global_y)
        """
        if player_global_pos:
            self.global_trail.append(player_global_pos)
    
    def draw_trail_on_map(self, map_img, color=(0, 255, 0), thickness=2):
        """
        在地图上绘制轨迹
        
        Args:
            map_img: 地图图像（需要是彩色）
            color: 轨迹颜色（默认绿色）
            thickness: 线条粗细
        
        Returns:
            绘制后的图像
        """
        if len(self.global_trail) < 2:
            return map_img
        
        # 绘制轨迹线
        trail_list = list(self.global_trail)
        for i in range(1, len(trail_list)):
            pt1 = trail_list[i-1]
            pt2 = trail_list[i]
            
            # 检查坐标是否在图像范围内
            h, w = map_img.shape[:2]
            if (0 <= pt1[0] < w and 0 <= pt1[1] < h and
                0 <= pt2[0] < w and 0 <= pt2[1] < h):
                cv2.line(map_img, pt1, pt2, color, thickness)
        
        return map_img
    
    def reset(self):
        """重置追踪器"""
        self.last_position = None
        self.trail.clear()
        self.global_trail.clear()
