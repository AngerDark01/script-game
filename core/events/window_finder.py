from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from dataclasses import dataclass


DWMWA_EXTENDED_FRAME_BOUNDS = 9


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


@dataclass
class WindowInfo:
    hwnd: int
    title: str
    class_name: str
    rect: dict[str, int]


def set_process_dpi_awareness() -> str:
    if os.name != "nt":
        return "non-windows"
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return "shcore.SetProcessDpiAwareness(2)"
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
            return "user32.SetProcessDPIAware()"
        except Exception as exc:
            return f"failed: {type(exc).__name__}: {exc}"


def find_game_window(title_substring: str = "Torchlight", class_substring: str = "UnrealWindow") -> WindowInfo | None:
    user32 = ctypes.windll.user32
    user32.EnumWindows.argtypes = [ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM), wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetClassNameW.restype = ctypes.c_int
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
    user32.GetWindowRect.restype = wintypes.BOOL

    title_need = title_substring.lower().strip()
    class_need = class_substring.lower().strip()
    matches: list[WindowInfo] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def enum_proc(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        title = _get_window_text(user32, int(hwnd))
        class_name = _get_class_name(user32, int(hwnd))
        title_ok = not title_need or title_need in title.lower()
        class_ok = not class_need or class_need in class_name.lower()
        if title_ok or class_ok:
            rect = _window_rect(user32, int(hwnd))
            if rect:
                matches.append(WindowInfo(int(hwnd), title, class_name, rect))
        return True

    user32.EnumWindows(enum_proc, 0)
    if not matches:
        return None
    matches.sort(key=lambda item: item.rect["width"] * item.rect["height"], reverse=True)
    return matches[0]


def primary_screen_rect() -> dict[str, int]:
    user32 = ctypes.windll.user32
    return {
        "left": 0,
        "top": 0,
        "width": int(user32.GetSystemMetrics(0)),
        "height": int(user32.GetSystemMetrics(1)),
    }


def _get_window_text(user32, hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def _get_class_name(user32, hwnd: int) -> str:
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buffer, 256)
    return buffer.value


def _window_rect(user32, hwnd: int) -> dict[str, int] | None:
    rect = RECT()
    try:
        dwmapi = ctypes.windll.dwmapi
        if dwmapi.DwmGetWindowAttribute(
            wintypes.HWND(hwnd),
            wintypes.DWORD(DWMWA_EXTENDED_FRAME_BOUNDS),
            ctypes.byref(rect),
            ctypes.sizeof(rect),
        ) == 0:
            pass
        elif not user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect)):
            return None
    except Exception:
        if not user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect)):
            return None

    width = int(rect.right - rect.left)
    height = int(rect.bottom - rect.top)
    if width <= 0 or height <= 0:
        return None
    return {"left": int(rect.left), "top": int(rect.top), "width": width, "height": height}

