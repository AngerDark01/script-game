from __future__ import annotations

import pydirectinput

from core.input.click_diagnostics import format_window_info
from core.input.click_executor import send_click
from core.input.screen_bounds import clamp_screen_pos, screen_height_from_driver_or_size

try:
    from core.input.win32_driver import InputDriver
except Exception:  # pragma: no cover - non-Windows fallback
    InputDriver = None


def screen_height(controller, driver=None):
    size = controller._safe_pydirectinput_call("size")
    return screen_height_from_driver_or_size(driver, size)


def send_controller_click(controller, x: int, y: int, driver=None) -> None:
    click_info = send_click(
        x=x,
        y=y,
        input_backend=controller.input_backend,
        driver=driver,
        click_button=controller.click_button,
        click_hold_seconds=controller.click_hold_seconds,
        click_move_delay_seconds=controller.click_move_delay_seconds,
        confirm_after_click=controller.confirm_after_click,
        confirm_click_delay_seconds=controller.confirm_click_delay_seconds,
        confirm_click_hold_seconds=controller.confirm_click_hold_seconds,
    )
    if controller.last_click_info is not None:
        controller.last_click_info.update(click_info)


def get_input_driver(controller):
    if controller._input_driver_initialized:
        return controller.input_driver
    controller._input_driver_initialized = True
    if InputDriver is None:
        controller.input_driver = None
        return None
    try:
        controller.input_driver = InputDriver()
    except Exception as exc:
        print(f"InputDriver unavailable, using pydirectinput fallback: {exc}")
        controller.input_driver = None
    return controller.input_driver


def clamp_controller_screen_pos(controller, screen_pos: tuple[int, int]) -> tuple[int, int]:
    driver = controller._get_input_driver()
    return clamp_screen_pos(
        screen_pos,
        screen_width=getattr(driver, "screen_width", None) if driver else None,
        screen_height=getattr(driver, "screen_height", None) if driver else None,
        margin=controller.screen_margin,
    )


def safe_pydirectinput_call(name: str):
    func = getattr(pydirectinput, name, None)
    if not callable(func):
        return None
    try:
        return func()
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"


def format_controller_window_info(window_info) -> str:
    return format_window_info(window_info)
