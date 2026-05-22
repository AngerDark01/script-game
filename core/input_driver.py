import ctypes
from ctypes import wintypes
import time

# Windows API Constants
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
GA_ROOT = 2


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]

class InputDriver:
    """
    Windows Input Driver using ctypes (SetCursorPos + mouse_event)
    Simple and robust for MVP.
    """
    def __init__(self):
        self.user32 = ctypes.windll.user32
        self.user32.WindowFromPoint.argtypes = [wintypes.POINT]
        self.user32.WindowFromPoint.restype = wintypes.HWND
        self.user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        self.user32.GetAncestor.restype = wintypes.HWND
        self.user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        self.user32.SetForegroundWindow.restype = wintypes.BOOL
        self.user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        self.user32.GetWindowTextLengthW.restype = ctypes.c_int
        self.user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        self.user32.GetWindowTextW.restype = ctypes.c_int
        self.user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        self.user32.GetClassNameW.restype = ctypes.c_int
        self.user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        self.user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        self.user32.GetForegroundWindow.argtypes = []
        self.user32.GetForegroundWindow.restype = wintypes.HWND
        self.user32.GetCursorPos.restype = wintypes.BOOL
        self.user32.GetClipCursor.argtypes = [ctypes.POINTER(RECT)]
        self.user32.GetClipCursor.restype = wintypes.BOOL
        self.screen_width = self.user32.GetSystemMetrics(0)
        self.screen_height = self.user32.GetSystemMetrics(1)

    def move_to(self, x, y):
        """Move mouse to absolute screen coordinates (x, y)"""
        # Ensure coordinates are integers
        x = int(x)
        y = int(y)
        return bool(self.user32.SetCursorPos(x, y))

    def cursor_pos(self):
        """Return current cursor position from Win32 GetCursorPos."""
        point = wintypes.POINT()
        if not self.user32.GetCursorPos(ctypes.byref(point)):
            return None
        return int(point.x), int(point.y)

    def clip_cursor_rect(self):
        """Return current ClipCursor rectangle, if Win32 exposes one."""
        rect = RECT()
        if not self.user32.GetClipCursor(ctypes.byref(rect)):
            return None
        return {
            "left": int(rect.left),
            "top": int(rect.top),
            "right": int(rect.right),
            "bottom": int(rect.bottom),
        }

    def foreground_window(self):
        """Return current foreground top-level HWND."""
        hwnd = self.user32.GetForegroundWindow()
        return int(hwnd) if hwnd else None

    def window_from_point(self, x, y):
        """Return the root HWND under an absolute screen point."""
        point = wintypes.POINT(int(x), int(y))
        hwnd = self.user32.WindowFromPoint(point)
        if not hwnd:
            return None
        root = self.user32.GetAncestor(hwnd, GA_ROOT)
        return root or hwnd

    def focus_window_at(self, x, y):
        """Try to focus the top-level window under an absolute screen point."""
        hwnd = self.window_from_point(x, y)
        if not hwnd:
            return None
        self.user32.SetForegroundWindow(hwnd)
        return int(hwnd)

    def describe_window_at(self, x, y):
        """Return diagnostic information for the root window under a screen point."""
        hwnd = self.window_from_point(x, y)
        return self.describe_window(hwnd)

    def describe_window(self, hwnd):
        """Return diagnostic information for a top-level window handle."""
        if not hwnd:
            return None

        pid = wintypes.DWORD(0)
        self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

        title = ""
        length = self.user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buffer = ctypes.create_unicode_buffer(length + 1)
            self.user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = buffer.value

        class_buffer = ctypes.create_unicode_buffer(256)
        self.user32.GetClassNameW(hwnd, class_buffer, 256)

        return {
            "hwnd": int(hwnd),
            "pid": int(pid.value),
            "class_name": class_buffer.value,
            "title": title,
        }

    def mouse_down(self, button='left'):
        """Press a mouse button at the current cursor position."""
        dwFlags = MOUSEEVENTF_LEFTDOWN
        if button == 'right':
            dwFlags = MOUSEEVENTF_RIGHTDOWN
        self.user32.mouse_event(dwFlags, 0, 0, 0, 0)

    def mouse_up(self, button='left'):
        """Release a mouse button at the current cursor position."""
        dwFlags = MOUSEEVENTF_LEFTUP
        if button == 'right':
            dwFlags = MOUSEEVENTF_RIGHTUP
        self.user32.mouse_event(dwFlags, 0, 0, 0, 0)

    def click(self, x=None, y=None, button='left', hold_seconds=0.08, move_delay=0.05):
        """Click at current position or specific coordinates"""
        if x is not None and y is not None:
            self.move_to(x, y)
            time.sleep(max(0.0, float(move_delay))) # Small delay for stability

        self.mouse_down(button)
        time.sleep(max(0.0, float(hold_seconds)))
        self.mouse_up(button)

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
