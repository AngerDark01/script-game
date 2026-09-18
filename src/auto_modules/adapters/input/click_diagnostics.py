from __future__ import annotations


def collect_window_diagnostics(driver, x: int, y: int) -> dict:
    """Collect best-effort window and Win32 cursor diagnostics for a click point."""
    info = {
        "target_window": None,
        "foreground_window": None,
        "clip_cursor_rect": None,
        "win_cursor_before": None,
    }
    if not driver:
        return info

    if hasattr(driver, "describe_window_at"):
        info["target_window"] = driver.describe_window_at(x, y)
    elif hasattr(driver, "window_from_point"):
        hwnd = driver.window_from_point(x, y)
        info["target_window"] = {"hwnd": int(hwnd)} if hwnd else None

    foreground_window = None
    if hasattr(driver, "foreground_window"):
        foreground_window = driver.foreground_window()
    if hasattr(driver, "describe_window") and foreground_window:
        info["foreground_window"] = driver.describe_window(foreground_window)

    if hasattr(driver, "clip_cursor_rect"):
        info["clip_cursor_rect"] = driver.clip_cursor_rect()
    if hasattr(driver, "cursor_pos"):
        info["win_cursor_before"] = driver.cursor_pos()

    return info


def focus_window_at(driver, x: int, y: int):
    """Focus the top-level window under a point if the driver supports it."""
    if not driver or not hasattr(driver, "focus_window_at"):
        return None
    return driver.focus_window_at(x, y)


def win_cursor_pos(driver):
    """Return Win32 cursor position if available."""
    if not driver or not hasattr(driver, "cursor_pos"):
        return None
    return driver.cursor_pos()


def format_window_info(window_info) -> str:
    """Format window diagnostics for compact log output."""
    if not window_info:
        return "None"
    hwnd = window_info.get("hwnd")
    pid = window_info.get("pid")
    class_name = window_info.get("class_name") or ""
    title = window_info.get("title") or ""
    if len(title) > 40:
        title = title[:37] + "..."
    return f"hwnd={hwnd},pid={pid},class='{class_name}',title='{title}'"
