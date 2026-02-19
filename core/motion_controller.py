import pydirectinput

class MotionController:
    """
    运动控制模块 V2
    负责将大地图的导航目标转换为精确的屏幕点击操作。
    """
    
    def __init__(self):
        self.game_screen_center = None
        self.movement_scale_factor = 15
        self.control_enabled = False

    def set_params(self, game_screen_center: tuple, movement_scale_factor: float):
        """设置运动控制的核心参数"""
        self.game_screen_center = game_screen_center
        self.movement_scale_factor = movement_scale_factor

    def set_control_enabled(self, enabled: bool):
        """开启/关闭实际鼠标控制"""
        self.control_enabled = enabled
        print(f"Motion Control Enabled: {enabled}")

    def move_to_map_target(self, player_global_pos: tuple, target_global_pos: tuple):
        """
        计算并执行从玩家位置到目标位置的移动点击。
        这是外部调用的主要接口。
        """
        if not self.control_enabled:
            print("Motion control is disabled. Skipping move.")
            return

        if not self.game_screen_center:
            print("Error: Game screen center is not calibrated.")
            return

        # 1. 计算目标屏幕坐标
        target_screen_pos = self._calculate_target_screen_position(
            player_global_pos, target_global_pos
        )

        # 2. 执行点击
        self._execute_click(target_screen_pos)

    def _calculate_target_screen_position(self, player_global_pos: tuple, target_global_pos: tuple) -> tuple[int, int]:
        """
        核心算法：将地图坐标的位移转换为屏幕坐标的位移。
        """
        # 计算地图上的位移向量 (从玩家到目标)
        delta_map_x = target_global_pos[0] - player_global_pos[0]
        delta_map_y = target_global_pos[1] - player_global_pos[1]

        # 应用运动映射比例，将地图位移转换为屏幕位移
        delta_screen_x = delta_map_x * self.movement_scale_factor
        delta_screen_y = delta_map_y * self.movement_scale_factor

        # 基于已校准的角色中心，计算最终的屏幕点击坐标
        target_screen_x = self.game_screen_center[0] + delta_screen_x
        target_screen_y = self.game_screen_center[1] + delta_screen_y
        
        return int(target_screen_x), int(target_screen_y)

    def _execute_click(self, screen_pos: tuple[int, int]):
        """执行移动和点击操作"""
        x, y = screen_pos
        print(f"Executing click at screen coordinates: ({x}, {y})")
        pydirectinput.click(x, y)

