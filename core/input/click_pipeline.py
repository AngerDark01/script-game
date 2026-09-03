from __future__ import annotations

from core.input.click_diagnostics import collect_window_diagnostics, focus_window_at, win_cursor_pos
from core.input.click_executor import fallback_pydirect_click


def execute_click(controller, screen_pos: tuple[int, int]) -> None:
    """Execute the MotionController click pipeline against a screen point."""
    requested_pos = (int(screen_pos[0]), int(screen_pos[1]))
    x, y = requested_pos
    driver = None
    focused_hwnd = None
    target_window = None
    if controller.input_backend == "win32_mouse_event" or controller.debug_click_target or controller.focus_before_click:
        driver = controller._get_input_driver()

    guarded_pos, guard_info = controller._apply_bottom_click_guard((x, y), driver=driver)
    x, y = guarded_pos
    pre_clamp_pos = (x, y)
    if controller.clamp_to_screen:
        x, y = controller._clamp_screen_pos((x, y))
    clamped = pre_clamp_pos != (x, y)
    if controller.last_click_info is not None:
        controller.last_click_info["screen_pos_requested"] = requested_pos
        controller.last_click_info["screen_pos_after_bottom_guard"] = pre_clamp_pos
        controller.last_click_info["screen_pos"] = (x, y)
        controller.last_click_info["screen_pos_clamped"] = clamped
        controller.last_click_info["bottom_guard"] = guard_info

    map_delta = controller.last_click_info.get("map_delta", (0.0, 0.0))
    foreground_info = None
    clip_rect = None
    win_cursor_before = None
    if controller.debug_click_target and driver:
        try:
            diagnostics = collect_window_diagnostics(driver, x, y)
            target_window = diagnostics.get("target_window")
            foreground_info = diagnostics.get("foreground_window")
            clip_rect = diagnostics.get("clip_cursor_rect")
            win_cursor_before = diagnostics.get("win_cursor_before")
            if controller.last_click_info is not None:
                controller.last_click_info["target_window"] = target_window
                controller.last_click_info["foreground_window"] = foreground_info
                controller.last_click_info["clip_cursor_rect"] = clip_rect
                controller.last_click_info["win_cursor_before"] = win_cursor_before
        except Exception as exc:
            print(f"Window diagnostic at click point failed: {exc}")

    if controller.focus_before_click and driver and hasattr(driver, "focus_window_at"):
        try:
            focused_hwnd = focus_window_at(driver, x, y)
            controller.last_click_info["focused_hwnd"] = focused_hwnd
        except Exception as exc:
            print(f"Window focus before click failed: {exc}")

    pydirect_size = controller._safe_pydirectinput_call("size")
    cursor_before = controller._safe_pydirectinput_call("position")
    if controller.last_click_info is not None:
        controller.last_click_info["pydirectinput_size"] = pydirect_size
        controller.last_click_info["cursor_before"] = cursor_before

    print(
        "Executing movement click: "
        f"requested=({requested_pos[0]}, {requested_pos[1]}), "
        f"screen=({x}, {y}), "
        f"clamped={clamped}, "
        f"radius={controller.last_click_info.get('screen_radius', 0):.1f}, "
        f"precision_cap={controller.last_click_info.get('precision_radius_cap', None)}, "
        f"map_delta=({map_delta[0]:.1f}, {map_delta[1]:.1f}), "
        f"backend={controller.input_backend}, "
        f"pydi_size={pydirect_size}, "
        f"cursor_before={cursor_before}, "
        f"win_cursor_before={win_cursor_before}, "
        f"bottom_guard={guard_info}, "
        f"target_window={controller._format_window_info(target_window)}, "
        f"foreground={controller._format_window_info(foreground_info)}, "
        f"clip={clip_rect}, "
        f"focused_hwnd={focused_hwnd}, "
        f"confirm={controller.confirm_after_click}"
    )
    try:
        controller._send_click(x, y, driver=driver)
        cursor_after = controller._safe_pydirectinput_call("position")
        try:
            win_cursor_after = win_cursor_pos(driver)
        except Exception:
            win_cursor_after = None
        if controller.last_click_info is not None:
            controller.last_click_info["cursor_after"] = cursor_after
            controller.last_click_info["win_cursor_after"] = win_cursor_after
        print(f"Movement click sent: cursor_after={cursor_after}, win_cursor_after={win_cursor_after}")
        return
    except Exception as exc:
        print(f"{controller.input_backend} click failed, falling back to pydirectinput: {exc}")

    fallback_pydirect_click(x, y, click_button=controller.click_button)
