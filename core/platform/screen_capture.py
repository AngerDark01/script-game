"""
跨平台屏幕捕获工具 - 正方形截图版
优先使用 mss（性能最优）
支持正方形截图和中心点定位
"""

import numpy as np
import cv2


class SquareScreenCapture:
    """正方形屏幕捕获接口"""

    def __init__(self):
        """初始化，自动选择最快的捕获方法"""
        self.method = None
        self.sct = None
        self._init_capture_method()

    def _init_capture_method(self):
        """初始化最优捕获方法"""
        # 优先使用 mss（最快）
        try:
            import mss
            self.sct = mss.mss()
            self.method = 'mss'
            print("[OK] 使用 MSS 进行屏幕捕获")
            return
        except ImportError:
            pass

        # 备选：PIL ImageGrab
        try:
            from PIL import ImageGrab
            self.method = 'pil'
            print("[OK] 使用 PIL ImageGrab 进行屏幕捕获")
            return
        except ImportError:
            pass

        raise RuntimeError("无法找到可用的截图工具！请安装: pip install mss")

    def capture_square(self, center_x, center_y, size):
        """
        捕获正方形区域

        Args:
            center_x: 中心点X坐标（物理像素）
            center_y: 中心点Y坐标（物理像素）
            size: 正方形边长（物理像素）

        Returns:
            numpy array (BGR格式)
        """
        half_size = size // 2
        x = center_x - half_size
        y = center_y - half_size
        
        return self.capture(x, y, size, size)

    def capture(self, x, y, width, height):
        """
        捕获指定屏幕区域

        Args:
            x: 左上角X坐标（物理像素）
            y: 左上角Y坐标（物理像素）
            width: 宽度（物理像素）
            height: 高度（物理像素）

        Returns:
            numpy array (BGR格式)
        """
        if self.method == 'mss':
            return self._capture_mss(x, y, width, height)
        elif self.method == 'pil':
            return self._capture_pil(x, y, width, height)
        else:
            raise RuntimeError("未初始化捕获方法")

    def _capture_mss(self, x, y, width, height):
        """使用 mss 捕获"""
        monitor = {
            'left': int(x),
            'top': int(y),
            'width': int(width),
            'height': int(height)
        }

        screenshot = self.sct.grab(monitor)
        img = np.array(screenshot)

        # BGRA -> BGR
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

        return img

    def _capture_pil(self, x, y, width, height):
        """使用 PIL 捕获"""
        from PIL import ImageGrab

        bbox = (int(x), int(y), int(x + width), int(y + height))
        screenshot = ImageGrab.grab(bbox=bbox)
        img = np.array(screenshot)

        # RGB -> BGR
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

        return img

    def close(self):
        """关闭捕获器，释放资源"""
        if self.sct:
            self.sct.close()

    def __del__(self):
        """析构函数"""
        self.close()
