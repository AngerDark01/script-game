import sys
import types
import unittest


PYDIRECT_CLICKS = []
PYDIRECT_DOWNS = []
PYDIRECT_UPS = []


sys.modules["pydirectinput"] = types.SimpleNamespace(
    click=lambda *args, **kwargs: PYDIRECT_CLICKS.append((args, kwargs)),
    mouseDown=lambda *args, **kwargs: PYDIRECT_DOWNS.append((args, kwargs)),
    mouseUp=lambda *args, **kwargs: PYDIRECT_UPS.append((args, kwargs)),
    size=lambda: (100, 80),
    position=lambda: (11, 22),
)

from core.motion_controller import MotionController


class FakeInputDriver:
    def __init__(self, screen_width=100, screen_height=80):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.focus_calls = []
        self.window_calls = []
        self.click_calls = []
        self.move_calls = []
        self.cursor = (11, 22)

    def move_to(self, x, y):
        self.move_calls.append((x, y))
        self.cursor = (x, y)
        return True

    def cursor_pos(self):
        return self.cursor

    def clip_cursor_rect(self):
        return {"left": 0, "top": 0, "right": self.screen_width, "bottom": self.screen_height}

    def foreground_window(self):
        return 2222

    def describe_window(self, hwnd):
        return {
            "hwnd": int(hwnd),
            "pid": 3333,
            "class_name": "GameWindow",
            "title": "Test Game",
        }

    def window_from_point(self, x, y):
        self.window_calls.append((x, y))
        return 2222

    def describe_window_at(self, x, y):
        self.window_calls.append((x, y))
        return {
            "hwnd": 2222,
            "pid": 3333,
            "class_name": "GameWindow",
            "title": "Test Game",
        }

    def focus_window_at(self, x, y):
        self.focus_calls.append((x, y))
        return 1234

    def click(self, x, y, button="left", hold_seconds=0.0, move_delay=0.0):
        self.click_calls.append((x, y, button, hold_seconds, move_delay))
        self.move_to(x, y)


class MotionControllerTest(unittest.TestCase):
    def test_short_map_delta_uses_min_click_radius(self):
        controller = MotionController()
        controller.set_params(
            game_screen_center=(1000, 500),
            movement_scale_factor=1.0,
            movement_min_click_radius=180,
            movement_max_click_radius=360,
        )

        screen_pos = controller._calculate_target_screen_position((0, 0), (10, 0))

        self.assertEqual(screen_pos, (1180, 500))
        self.assertEqual(controller.last_click_info["screen_radius"], 180)

    def test_long_map_delta_is_clamped_to_max_click_radius(self):
        controller = MotionController()
        controller.set_params(
            game_screen_center=(1000, 500),
            movement_scale_factor=1.0,
            movement_min_click_radius=180,
            movement_max_click_radius=360,
        )

        screen_pos = controller._calculate_target_screen_position((0, 0), (1000, 0))

        self.assertEqual(screen_pos, (1360, 500))
        self.assertEqual(controller.last_click_info["screen_radius"], 360)

    def test_zero_delta_does_not_click(self):
        controller = MotionController()
        controller.set_params(
            game_screen_center=(1000, 500),
            movement_scale_factor=1.0,
            movement_min_click_radius=180,
            movement_max_click_radius=360,
        )

        screen_pos = controller._calculate_target_screen_position((10, 10), (10, 10))

        self.assertIsNone(screen_pos)
        self.assertIsNone(controller.last_click_info["screen_pos"])

    def test_execute_click_uses_requested_position_by_default(self):
        PYDIRECT_CLICKS.clear()
        PYDIRECT_DOWNS.clear()
        PYDIRECT_UPS.clear()
        driver = FakeInputDriver()
        controller = MotionController(input_driver=driver)
        controller.control_enabled = True
        controller.last_click_info = {
            "map_delta": (1.0, 1.0),
            "screen_radius": 50.0,
        }

        controller._execute_click((120, -10))

        self.assertEqual(driver.focus_calls, [])
        self.assertEqual(driver.window_calls, [(120, -10)])
        self.assertEqual(driver.move_calls, [(120, -10)])
        self.assertEqual(driver.click_calls, [(120, -10, "primary", 0.05, 0.02)])
        self.assertEqual(PYDIRECT_CLICKS, [])
        self.assertEqual(PYDIRECT_DOWNS, [])
        self.assertEqual(PYDIRECT_UPS, [])
        self.assertEqual(controller.last_click_info["screen_pos_requested"], (120, -10))
        self.assertEqual(controller.last_click_info["screen_pos"], (120, -10))
        self.assertFalse(controller.last_click_info["screen_pos_clamped"])
        self.assertFalse(controller.last_click_info["confirm_click"])
        self.assertEqual(controller.last_click_info["target_window"]["hwnd"], 2222)
        self.assertEqual(controller.last_click_info["pydirectinput_size"], (100, 80))
        self.assertEqual(controller.last_click_info["cursor_before"], (11, 22))
        self.assertEqual(controller.last_click_info["cursor_after"], (11, 22))
        self.assertEqual(controller.last_click_info["win_cursor_before"], (11, 22))
        self.assertEqual(controller.last_click_info["win_cursor_after"], (120, -10))
        self.assertTrue(controller.last_click_info["moved_by_driver"])
        self.assertNotIn("focused_hwnd", controller.last_click_info)

    def test_execute_click_can_clamp_to_screen_when_explicitly_enabled(self):
        PYDIRECT_CLICKS.clear()
        PYDIRECT_DOWNS.clear()
        PYDIRECT_UPS.clear()
        driver = FakeInputDriver()
        controller = MotionController(input_driver=driver)
        controller.clamp_to_screen = True
        controller.last_click_info = {
            "map_delta": (1.0, 1.0),
            "screen_radius": 50.0,
        }

        controller._execute_click((120, -10))

        self.assertEqual(driver.move_calls, [(97, 2)])
        self.assertEqual(driver.click_calls, [(97, 2, "primary", 0.05, 0.02)])
        self.assertEqual(PYDIRECT_CLICKS, [])
        self.assertEqual(controller.last_click_info["screen_pos_requested"], (120, -10))
        self.assertEqual(controller.last_click_info["screen_pos"], (97, 2))
        self.assertTrue(controller.last_click_info["screen_pos_clamped"])

    def test_execute_click_can_focus_target_window_when_enabled(self):
        PYDIRECT_CLICKS.clear()
        PYDIRECT_DOWNS.clear()
        PYDIRECT_UPS.clear()
        driver = FakeInputDriver()
        controller = MotionController(input_driver=driver)
        controller.focus_before_click = True
        controller.confirm_after_click = False
        controller.last_click_info = {
            "map_delta": (1.0, 1.0),
            "screen_radius": 50.0,
        }

        controller._execute_click((50, 50))

        self.assertEqual(driver.focus_calls, [(50, 50)])
        self.assertEqual(driver.move_calls, [(50, 50)])
        self.assertEqual(driver.click_calls, [(50, 50, "primary", 0.05, 0.02)])
        self.assertEqual(PYDIRECT_CLICKS, [])
        self.assertEqual(PYDIRECT_DOWNS, [])
        self.assertEqual(PYDIRECT_UPS, [])
        self.assertEqual(controller.last_click_info["focused_hwnd"], 1234)
        self.assertFalse(controller.last_click_info["confirm_click"])

    def test_bottom_click_guard_shortens_click_before_bottom_ui(self):
        PYDIRECT_CLICKS.clear()
        driver = FakeInputDriver(screen_width=100, screen_height=100)
        controller = MotionController(input_driver=driver)
        controller.game_screen_center = (50, 40)
        controller.bottom_click_guard_pixels = 20
        controller.bottom_click_guard_margin = 5
        controller.last_click_info = {
            "map_delta": (1.0, 3.0),
            "screen_radius": 50.0,
        }

        controller._execute_click((70, 90))

        self.assertEqual(driver.click_calls, [(64, 75, "primary", 0.05, 0.02)])
        self.assertEqual(controller.last_click_info["screen_pos_requested"], (70, 90))
        self.assertEqual(controller.last_click_info["screen_pos_after_bottom_guard"], (64, 75))
        self.assertEqual(controller.last_click_info["screen_pos"], (64, 75))
        self.assertFalse(controller.last_click_info["screen_pos_clamped"])
        self.assertTrue(controller.last_click_info["bottom_guard"]["applied"])
        self.assertEqual(controller.last_click_info["bottom_guard"]["forbidden_top"], 80)
        self.assertEqual(PYDIRECT_CLICKS, [])


if __name__ == "__main__":
    unittest.main()
