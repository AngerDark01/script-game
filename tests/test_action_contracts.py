import unittest

from core.actions import (
    ActionCommand,
    ActionKind,
    GamepadStickTarget,
    KeyboardTarget,
    VirtualControllerRoute,
)


class ActionContractTests(unittest.TestCase):
    def test_gamepad_stick_target_rejects_out_of_range_axis_values(self):
        route = VirtualControllerRoute(controller=1, source="test", ttl_ms=250)

        with self.assertRaises(ValueError):
            GamepadStickTarget(route=route, stick="left", x=32768, y=0)

    def test_gamepad_route_rejects_invalid_controller_source_and_ttl(self):
        with self.assertRaises(ValueError):
            VirtualControllerRoute(controller=3, source="test", ttl_ms=250)
        with self.assertRaises(ValueError):
            VirtualControllerRoute(controller=1, source="", ttl_ms=250)
        with self.assertRaises(ValueError):
            VirtualControllerRoute(controller=1, source="test", ttl_ms=0)

    def test_command_requires_compatible_kind_and_target(self):
        target = KeyboardTarget(("ctrl", "s"))

        with self.assertRaises(ValueError):
            ActionCommand(ActionKind.GAMEPAD_STICK, target)

    def test_key_down_requires_exactly_one_key(self):
        with self.assertRaises(ValueError):
            ActionCommand(ActionKind.KEY_DOWN, KeyboardTarget(("ctrl", "s")))


if __name__ == "__main__":
    unittest.main()
