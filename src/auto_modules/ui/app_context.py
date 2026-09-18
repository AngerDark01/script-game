from PySide6.QtCore import QObject

from .composition.services import CoreServices, create_core_services

class AppContext(QObject):
    """
    应用上下文，持有核心业务逻辑对象和共享状态。
    """
    def __init__(self, parent=None, *, services: CoreServices | None = None):
        super().__init__(parent)
        
        # 核心组件
        services = services or create_core_services()
        self.screen_capture = services.screen_capture
        self.recognizer = services.recognizer
        self.stitcher = services.stitcher
        self.tracker = services.tracker
        self.path_finder = services.path_finder

        # 共享状态
        self.monitor_region = None
        self.monitor_logical_center = None
        self.monitor_size = 320
        self.monitoring = False
