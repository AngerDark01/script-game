import ctypes
import time
import math

# Windows API Constants
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010

class InputDriver:
    """
    Windows Input Driver using ctypes (SetCursorPos + mouse_event)
    Simple and robust for MVP.
    """
    def __init__(self):
        self.user32 = ctypes.windll.user32
        self.screen_width = self.user32.GetSystemMetrics(0)
        self.screen_height = self.user32.GetSystemMetrics(1)

    def move_to(self, x, y):
        """Move mouse to absolute screen coordinates (x, y)"""
        # Ensure coordinates are integers
        x = int(x)
        y = int(y)
        self.user32.SetCursorPos(x, y)

    def click(self, x=None, y=None, button='left'):
        """Click at current position or specific coordinates"""
        if x is not None and y is not None:
            self.move_to(x, y)
            time.sleep(0.05) # Small delay for stability
            
        dwFlags = MOUSEEVENTF_LEFTDOWN | MOUSEEVENTF_LEFTUP
        if button == 'right':
            dwFlags = MOUSEEVENTF_RIGHTDOWN | MOUSEEVENTF_RIGHTUP
            
        # mouse_event(dwFlags, dx, dy, dwData, dwExtraInfo)
        self.user32.mouse_event(dwFlags, 0, 0, 0, 0)

    def drag(self, x1, y1, x2, y2, duration=0.5):
        """Drag from (x1, y1) to (x2, y2)"""
        self.move_to(x1, y1)
        time.sleep(0.1)
        
        self.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.1)
        
        # Simple interpolation
        steps = 10
        for i in range(steps):
            tx = x1 + (x2 - x1) * (i + 1) / steps
            ty = y1 + (y2 - y1) * (i + 1) / steps
            self.move_to(tx, ty)
            time.sleep(duration / steps)
            
        self.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
