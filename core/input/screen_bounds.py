from __future__ import annotations


def screen_height_from_driver_or_size(driver, size) -> int | None:
    """Return screen height from the Win32 driver or pydirectinput.size()."""
    if driver and getattr(driver, "screen_height", None):
        return int(driver.screen_height)
    if isinstance(size, tuple) and len(size) >= 2:
        return int(size[1])
    return None


def clamp_screen_pos(screen_pos: tuple[int, int], *, screen_width, screen_height, margin: int) -> tuple[int, int]:
    """Clamp a screen point inside the process-visible screen bounds."""
    if not screen_width or not screen_height:
        return screen_pos

    margin = max(0, int(margin))
    max_x = max(0, int(screen_width) - 1 - margin)
    max_y = max(0, int(screen_height) - 1 - margin)
    min_x = min(margin, max_x)
    min_y = min(margin, max_y)
    x = min(max(int(screen_pos[0]), min_x), max_x)
    y = min(max(int(screen_pos[1]), min_y), max_y)
    return x, y
