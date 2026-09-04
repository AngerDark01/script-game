import unittest

from core.actions import (
    ActionCommand,
    ActionKind,
    GamepadStickTarget,
    KeyboardTarget,
    PointerTarget,
    VirtualControllerRoute,
)
from core.spatial import physical_screen_point


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

    def test_click_requires_a_pointer_target(self):
        command = ActionCommand(
            ActionKind.CLICK,
            PointerTarget(physical_screen_point(10, 20)),
        )

        self.assertIs(ActionKind.CLICK, command.kind)

        with self.assertRaises(ValueError):
            ActionCommand(ActionKind.CLICK, KeyboardTarget(("d",)))


if __name__ == "__main__":
    unittest.main()
