"""
实时小地图拼接系统 - 程序入口

使用方法:
    python main.py

功能:
    1. 画框选择游戏小地图区域
    1. 画框选择游戏小地图区域
    2. 实时监控并拼接地图
    3. HSV颜色识别 + 相位相关算法
    4. 高性能实时处理
"""

import ctypes
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import time
from ctypes import wintypes


DEBUG_CONSOLE_ENV = "MINIMAP_DEBUG_CONSOLE"
_RUNTIME_LOG_HANDLE = None
_SINGLE_INSTANCE_MUTEX_HANDLE = None
ERROR_ALREADY_EXISTS = 183
MAIN_WINDOW_TITLE = "\u5b9e\u65f6\u5c0f\u5730\u56fe\u62fc\u63a5\u7cfb\u7edf"


class _OutputTee:
    def __init__(self, *targets):
        self.targets = [target for target in targets if target is not None]
        self.encoding = "utf-8"
        self.errors = "replace"

    def write(self, text):
        for target in self.targets:
            try:
                target.write(text)
            except Exception:
                pass
        return len(text)

    def flush(self):
        for target in self.targets:
            try:
                target.flush()
            except Exception:
                pass

    def isatty(self):
        return any(bool(getattr(target, "isatty", lambda: False)()) for target in self.targets)


def _has_console_window():
    if os.name != "nt":
        return True
    try:
        return bool(ctypes.windll.kernel32.GetConsoleWindow())
    except Exception:
        return False


def _debug_console_enabled():
    return os.environ.get(DEBUG_CONSOLE_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def configure_runtime_output():
    """Use UTF-8 output and keep diagnostics in a log file even under pythonw."""
    global _RUNTIME_LOG_HANDLE
    if os.name == "nt":
        try:
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            ctypes.windll.kernel32.SetConsoleCP(65001)
        except Exception:
            pass

    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is not None and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

    log_dir = Path(__file__).resolve().parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "runtime.log"
    _RUNTIME_LOG_HANDLE = log_path.open("w", encoding="utf-8-sig", buffering=1)
    _RUNTIME_LOG_HANDLE.write(f"\n=== session {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")

    current_stdout = getattr(sys, "stdout", None)
    current_stderr = getattr(sys, "stderr", None)
    if _has_console_window() and _debug_console_enabled():
        sys.stdout = _OutputTee(current_stdout, _RUNTIME_LOG_HANDLE)
        sys.stderr = _OutputTee(current_stderr, _RUNTIME_LOG_HANDLE)
    else:
        sys.stdout = _RUNTIME_LOG_HANDLE
        sys.stderr = _RUNTIME_LOG_HANDLE


def hide_console_if_not_debugging():
    """Detach the console for GUI use; diagnostics remain in logs/runtime.log."""
    if os.name != "nt" or _debug_console_enabled():
        return
    try:
        ctypes.windll.kernel32.FreeConsole()
    except Exception:
        pass


configure_runtime_output()
hide_console_if_not_debugging()


def set_process_dpi_awareness():
    """Enable physical-pixel coordinates before Qt initializes."""
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


def is_running_as_admin():
    if os.name != "nt":
        return True
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin():
    """Relaunch the current Python process through UAC and return True on launch."""
    if os.name != "nt":
        return False
    if getattr(sys, "frozen", False):
        executable = sys.executable
        params = subprocess.list2cmdline(sys.argv[1:])
    else:
        executable = _gui_python_executable()
        params = subprocess.list2cmdline(sys.argv)
    result = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        executable,
        params,
        os.getcwd(),
        1,
    )
    return result > 32


def _gui_python_executable():
    if _debug_console_enabled():
        return sys.executable
    current = Path(sys.executable)
    if current.name.lower() in {"python.exe", "python3.exe"}:
        pythonw = current.with_name("pythonw.exe")
        if pythonw.exists():
            return str(pythonw)
    return sys.executable


def _single_instance_mutex_name():
    project_path = str(Path(__file__).resolve().parent).lower()
    digest = hashlib.sha1(project_path.encode("utf-8", errors="ignore")).hexdigest()[:16]
    return f"Local\\MinimapStitcher_{digest}"


def acquire_single_instance_lock():
    """Prevent two GUI instances from driving the game and event system at once."""
    global _SINGLE_INSTANCE_MUTEX_HANDLE
    if os.name != "nt":
        return True
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel32.CloseHandle.restype = wintypes.BOOL
        handle = kernel32.CreateMutexW(None, False, _single_instance_mutex_name())
        if not handle:
            print("Single-instance lock unavailable; continuing without lock.")
            return True
        if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(handle)
            print("Another minimap_stitcher instance is already running; exiting this instance.")
            return False
        _SINGLE_INSTANCE_MUTEX_HANDLE = handle
        print(f"Single-instance lock acquired: {_single_instance_mutex_name()}")
        return True
    except Exception as exc:
        print(f"Single-instance lock failed: {type(exc).__name__}: {exc}")
        return True


def has_existing_main_window() -> bool:
    """Detect already-running old builds that do not own the mutex lock."""
    if os.name != "nt":
        return False
    try:
        user32 = ctypes.windll.user32
        current_pid = os.getpid()
        found = ctypes.c_bool(False)

        enum_windows_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows.argtypes = (enum_windows_proc, wintypes.LPARAM)
        user32.EnumWindows.restype = wintypes.BOOL
        user32.IsWindowVisible.argtypes = (wintypes.HWND,)
        user32.IsWindowVisible.restype = wintypes.BOOL
        user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
        user32.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
        user32.GetWindowTextLengthW.restype = ctypes.c_int
        user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
        user32.GetWindowTextW.restype = ctypes.c_int

        def callback(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if int(pid.value) == current_pid:
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            if MAIN_WINDOW_TITLE in buffer.value:
                found.value = True
                return False
            return True

        user32.EnumWindows(enum_windows_proc(callback), 0)
        return bool(found.value)
    except Exception as exc:
        print(f"Existing-window check failed: {type(exc).__name__}: {exc}")
        return False


DPI_AWARENESS_RESULT = set_process_dpi_awareness()


if os.name == "nt" and not is_running_as_admin():
    print("需要管理员权限来向游戏窗口发送鼠标输入，正在请求 UAC 提权...")
    if relaunch_as_admin():
        sys.exit(0)
    print("管理员提权失败或被取消，程序退出。")
    sys.exit(1)

if not acquire_single_instance_lock():
    sys.exit(0)

if has_existing_main_window():
    print("Another minimap_stitcher window is already running; exiting this instance.")
    sys.exit(0)

from PySide6.QtWidgets import QApplication
from gui.main_window import MainWindow


def main():
    """主函数"""
    print("=" * 60)
    print("实时小地图拼接系统")
    print("=" * 60)
    print(f"DPI awareness: {DPI_AWARENESS_RESULT}")
    print(f"Admin: {is_running_as_admin()}")
    print()
    print("算法: 相位相关法 (cv2.phaseCorrelate)")
    print("特征: HSV颜色分割 + 二值化处理")
    print("性能: 10fps 实时处理")
    print()
    print("=" * 60)
    print()
    
    # 创建应用
    app = QApplication(sys.argv)
    
    # 创建主窗口
    window = MainWindow()
    window.show()
    
    print("√ 主窗口已启动")
    print()
    print("使用步骤:")
    print("  1. 点击'画框选择区域'按钮")
    print("  2. 在游戏小地图上拖动鼠标画框")
    print("  3. 按 ENTER 确认选择")
    print("  4. 点击'开始监控'启动拼接")
    print("  5. 玩游戏，自动构建完整地图!")
    print()
    print("=" * 60)
    
    # 运行应用
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
