import math
import time
from .input_driver import InputDriver

class MotionController:
    """
    运动控制模块
    负责计算移动向量并执行移动操作 (模拟鼠标点击)
    """
    
    def __init__(self):
        self.target_pos = None
        self.is_moving = False
        self.arrival_threshold = 20.0 # 到达目标的判定距离 (像素, 全局坐标系)
        
        # 输入驱动
        self.driver = InputDriver()
        self.control_enabled = False # 默认不开启实际控制
        
        # 屏幕参数
        # 自动获取屏幕中心
        self.screen_center = (self.driver.screen_width // 2, self.driver.screen_height // 2)
        self.draw_scale = 2.0 # 全局坐标到屏幕坐标的缩放比例 (Global = Screen * Scale)
        self.k_ratio = 10.0 # 映射系数 (Screen / Minimap)
        self.y_bias = 1.0 # 纵向移动补偿系数
        self.center_offset_y = 0 # 屏幕中心Y轴偏移量 (正数向下)
        
        # 点击控制
        self.last_click_time = 0
        self.click_interval = 0.2 # 点击间隔 (秒)
        self.max_click_radius = 300 # 最大点击半径 (屏幕像素)
        
    def set_target(self, target_pos):
        """设置新的导航目标"""
        self.target_pos = target_pos
        self.is_moving = True
        print(f"Target set to: {self.target_pos}")
        
    def stop(self):
        """停止移动"""
        self.is_moving = False
        self.target_pos = None
        
    def set_screen_params(self, center_x, center_y, size, y_bias=1.0, center_offset_y=0):
        """设置屏幕中心点和缩放比例"""
        # size 参数目前没有直接使用，但保留以备将来扩展
        self.screen_center = (center_x, center_y)
        self.y_bias = y_bias
        self.center_offset_y = center_offset_y
        print(f"MotionController params updated: center={self.screen_center}, y_bias={self.y_bias}, center_offset_y={self.center_offset_y}")
        
    def set_control_enabled(self, enabled):
        """开启/关闭实际鼠标控制"""
        self.control_enabled = enabled
        print(f"Motion Control Enabled: {enabled}")
        
    def update(self, current_pos):
        """
        根据当前位置计算控制指令并执行
        
        Args:
            current_pos (tuple): 当前全局坐标 (x, y)
            
        Returns:
            dict: 包含 'action' ('move' or 'stop'), 'vector' (dx, dy), 'distance'
        """
        if not self.is_moving or self.target_pos is None or current_pos is None:
            return {'action': 'stop'}
            
        cx, cy = current_pos
        tx, ty = self.target_pos
        
        # 计算距离 (全局坐标系)
        dx = tx - cx
        dy = ty - cy
        distance = math.sqrt(dx**2 + dy**2)
        
        # 判定是否到达
        if distance < self.arrival_threshold:
            self.is_moving = False
            print("Destination reached.")
            return {'action': 'stop', 'reason': 'arrived'}
            
        # 计算归一化方向向量
        if distance > 0:
            norm_dx = dx / distance
            norm_dy = dy / distance
        else:
            norm_dx, norm_dy = 0, 0
            
        # === 执行鼠标控制 ===
        if self.control_enabled:
            now = time.time()
            if now - self.last_click_time > self.click_interval:
                self._perform_click_move(norm_dx, norm_dy, distance)
                self.last_click_time = now
        
        return {
            'action': 'move',
            'vector': (norm_dx, norm_dy),
            'distance': distance,
            'target_angle': math.degrees(math.atan2(dy, dx))
        }

    def _perform_click_move(self, dx, dy, global_dist):
        """执行点击移动"""
        # 1. 将全局距离转换为屏幕距离
        # Minimap Dist = Global Dist / Draw Scale
        # Screen Dist = Minimap Dist * K Ratio
        minimap_dist = global_dist / self.draw_scale
        screen_dist = minimap_dist * self.k_ratio
        
        # 应用纵向补偿
        # 如果 dy > 0 (向下移动)，可能需要补偿
        # 但这里的 dx, dy 是归一化向量，我们直接在计算 click_y 时应用 y_bias 即可
        # 或者更准确地，在计算屏幕位移分量时应用
        
        # 2. 限制最大点击半径 (防止点到屏幕外面或UI上)
        if screen_dist > self.max_click_radius:
            screen_dist = self.max_click_radius
            
        # 3. 计算屏幕点击坐标
        # Center + Vector * Radius
        sc_x, sc_y = self.screen_center
        
        # 应用 Y 轴偏移 (Center Offset)
        # 实际的中心点 = 屏幕物理中心 + 偏移
        effective_center_y = sc_y + self.center_offset_y
        
        # 应用 Y 轴补偿: dy 分量乘以 y_bias
        # 注意：这里的 dx, dy 是归一化向量，乘以 screen_dist 得到位移分量
        offset_x = dx * screen_dist
        offset_y = dy * screen_dist * self.y_bias 
        
        click_x = sc_x + offset_x
        click_y = effective_center_y + offset_y
        
        # 4. 执行点击
        # print(f"Clicking at ({int(click_x)}, {int(click_y)})")
        self.driver.click(click_x, click_y)
