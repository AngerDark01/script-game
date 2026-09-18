import unittest

from auto_modules.core.actions import ActionCommand, ActionKind, KeyboardTarget, PointerTarget
from auto_modules.adapters.input import MotionControllerActionAdapter
from auto_modules.core.spatial import physical_screen_point


class _MotionController:
    def __init__(self, *, click_result=None, key_result=None):
        self.click_result = click_result
        self.key_result = key_result
        self.calls = []

    def click_screen_position(self, screen_pos, *, reason):
        self.calls.append(("click", screen_pos, reason))
        return self.click_result

    def press_key(self, key, *, reason):
        self.calls.append(("key", key, reason))
        return self.key_result


class MotionControllerActionAdapterTests(unittest.TestCase):
    def test_click_delegates_one_physical_point_to_legacy_controller(self):
        controller = _MotionController(click_result={"screen_pos": (12, 34)})
        adapter = MotionControllerActionAdapter(controller=controller, clock_ms=lambda: 100)

        result = adapter.execute(
            ActionCommand(ActionKind.CLICK, PointerTarget(physical_screen_point(12.4, 33.6)))
        )

        self.assertTrue(result.executed)
        self.assertEqual((12, 34), result.point)
        self.assertEqual([("click", (12, 34), "navigation_primitive_click")], controller.calls)

    def test_disabled_legacy_control_is_reported_as_a_skipped_command(self):
        controller = _MotionController(click_result=None)
        adapter = MotionControllerActionAdapter(controller=controller, clock_ms=lambda: 100)

        result = adapter.execute(
            ActionCommand(ActionKind.CLICK, PointerTarget(physical_screen_point(12, 34)))
        )

        self.assertFalse(result.executed)
        self.assertEqual((12, 34), result.point)

    def test_one_key_chord_delegates_to_legacy_key_press(self):
        controller = _MotionController(key_result={"key": "d"})
        adapter = MotionControllerActionAdapter(controller=controller, clock_ms=lambda: 100)

        result = adapter.execute(ActionCommand(ActionKind.KEY_CHORD, KeyboardTarget(("D",))))

        self.assertTrue(result.executed)
        self.assertEqual([("key", "d", "navigation_primitive_key")], controller.calls)

    def test_map_like_pointer_move_is_rejected_before_legacy_controller_io(self):
        controller = _MotionController(click_result={"screen_pos": (12, 34)})
        adapter = MotionControllerActionAdapter(controller=controller, clock_ms=lambda: 100)

        with self.assertRaises(ValueError):
            adapter.execute(ActionCommand(ActionKind.MOVE, PointerTarget(physical_screen_point(12, 34))))

        self.assertEqual([], controller.calls)


if __name__ == "__main__":
    unittest.main()
