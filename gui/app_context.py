import sys
import os
from PySide6.QtCore import QObject
from core import ScreenCapture, HSVRecognizer, MapStitcher, PlayerTracker, PathFinder

class AppContext(QObject):
    """
    应用上下文，持有核心业务逻辑对象和共享状态。
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 核心组件
        self.screen_capture = ScreenCapture()
        self.recognizer = HSVRecognizer()
        # 将画布调整为 5000x5000，足够大且性能更好
        self.stitcher = MapStitcher(canvas_size=5000)
        self.tracker = PlayerTracker()
        self.path_finder = PathFinder()

        # 共享状态
        self.monitor_region = None
        self.monitor_logical_center = None
        self.monitor_size = 200
        self.monitoring = False
        
        # 加载全局配置 (例如 HSV 参数)
        self.load_global_config()

    def load_global_config(self):
        """加载全局配置文件 (config.json)"""
        # 这个方法可以用来加载那些不随地图改变的配置
        # 比如一些默认的HSV参数，UI状态等
        # 目前暂时留空，逻辑可以从原主窗口的 load_saved_params 迁移过来
        pass

    def save_global_config(self):
        """保存全局配置文件"""
        pass
