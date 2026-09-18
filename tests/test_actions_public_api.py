"""Public import regression tests for the composable action library."""

import unittest


class ActionPublicApiTests(unittest.TestCase):
    def test_keyboard_and_virtual_gamepad_adapters_are_publicly_available(self):
        from auto_modules.core.actions import (
            ActionAdapter,
            ActionCommand,
            KeyboardActionAdapter,
            KeyboardTarget,
            VirtualControllerRoute,
            VirtualGamepadActionAdapter,
        )

        self.assertIsNotNone(ActionAdapter)
        self.assertIsNotNone(ActionCommand)
        self.assertIsNotNone(KeyboardActionAdapter)
        self.assertIsNotNone(KeyboardTarget)
        self.assertIsNotNone(VirtualControllerRoute)
        self.assertIsNotNone(VirtualGamepadActionAdapter)


if __name__ == "__main__":
    unittest.main()
