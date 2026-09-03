from __future__ import annotations

import time

import pydirectinput


def send_click(
    *,
    x: int,
    y: int,
    input_backend: str,
    driver,
    click_button: str,
    click_hold_seconds: float,
    click_move_delay_seconds: float,
    confirm_after_click: bool,
    confirm_click_delay_seconds: float,
    confirm_click_hold_seconds: float,
) -> dict:
    """Send a mouse click and return metadata about the selected backend path."""
    info = {
        "moved_by_driver": False,
        "confirm_click": False,
    }

    if input_backend == "win32_mouse_event" and driver and hasattr(driver, "click"):
        driver.click(
            int(x),
            int(y),
            button=click_button,
            hold_seconds=click_hold_seconds,
            move_delay=click_move_delay_seconds,
        )
        info["moved_by_driver"] = True
        return info

    pydirectinput.click(int(x), int(y), button=click_button)
    if not confirm_after_click:
        return info

    time.sleep(max(0.0, float(confirm_click_delay_seconds)))
    if hasattr(pydirectinput, "mouseDown") and hasattr(pydirectinput, "mouseUp"):
        pydirectinput.mouseDown(button=click_button)
        time.sleep(max(0.0, float(confirm_click_hold_seconds)))
        pydirectinput.mouseUp(button=click_button)
    else:
        pydirectinput.click(button=click_button)

    info["confirm_click"] = True
    return info


def fallback_pydirect_click(x: int, y: int, *, click_button: str) -> None:
    """Fallback click used when the preferred backend raises."""
    pydirectinput.click(int(x), int(y), button=click_button)
