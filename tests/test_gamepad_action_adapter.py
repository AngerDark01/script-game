import unittest

from core.actions import (
    ActionCommand,
    ActionKind,
    GamepadButtonTarget,
    GamepadResetTarget,
    GamepadStickTarget,
    GamepadTriggerTarget,
    KeyboardTarget,
    VirtualControllerRoute,
    VirtualGamepadActionAdapter,
)
from virtual_gamepad.client.python import VirtualGamepadClient
from virtual_gamepad.client.python.virtual_gamepad_client import JsonFileTransport


class _FakeGamepadDevice:
    def __init__(self):
        self.calls = []

    def button(self, button, action, source, ttl_ms, controller):
        self.calls.append(("button", button, action, source, ttl_ms, controller))

    def set_axis(self, axis, value, source, ttl_ms, controller):
        self.calls.append(("set_axis", axis, value, source, ttl_ms, controller))

    def set_trigger(self, trigger, value, source, ttl_ms, controller):
        self.calls.append(("set_trigger", trigger, value, source, ttl_ms, controller))

    def reset(self, controller):
        self.calls.append(("reset", controller))


class VirtualGamepadActionAdapterTests(unittest.TestCase):
    def test_stick_command_routes_both_axes_and_ttl_to_selected_controller(self):
        client = _FakeGamepadDevice()
        adapter = VirtualGamepadActionAdapter(device=client, clock_ms=lambda: 20)
        route = VirtualControllerRoute(controller=2, source="nav", ttl_ms=300)
        command = ActionCommand(
            ActionKind.GAMEPAD_STICK,
            GamepadStickTarget(route=route, stick="left", x=-12000, y=22000),
        )

        result = adapter.execute(command)

        self.assertEqual(
            [
                ("set_axis", "left_x", -12000, "nav", 300, 2),
                ("set_axis", "left_y", 22000, "nav", 300, 2),
            ],
            client.calls,
        )
        self.assertTrue(result.executed)
        self.assertEqual("virtual_gamepad", result.device_id)
        self.assertEqual(2, result.metadata["controller"])

    def test_button_trigger_and_reset_are_forwarded_without_host_lifecycle_calls(self):
        client = _FakeGamepadDevice()
        adapter = VirtualGamepadActionAdapter(device=client, clock_ms=lambda: 20)
        route = VirtualControllerRoute(controller=1, source="combat", ttl_ms=180)

        adapter.execute(ActionCommand(ActionKind.GAMEPAD_BUTTON, GamepadButtonTarget(route, "A", pressed=True)))
        adapter.execute(ActionCommand(ActionKind.GAMEPAD_BUTTON, GamepadButtonTarget(route, "A", pressed=False)))
        adapter.execute(ActionCommand(ActionKind.GAMEPAD_TRIGGER, GamepadTriggerTarget(route, "rt", 255)))
        adapter.execute(ActionCommand(ActionKind.GAMEPAD_RESET, GamepadResetTarget(route)))

        self.assertEqual(
            [
                ("button", "A", "press", "combat", 180, 1),
                ("button", "A", "release", "combat", 180, 1),
                ("set_trigger", "right", 255, "combat", 180, 1),
                ("reset", 1),
            ],
            client.calls,
        )

    def test_keyboard_command_is_rejected_before_gamepad_device_io(self):
        client = _FakeGamepadDevice()
        adapter = VirtualGamepadActionAdapter(device=client, clock_ms=lambda: 20)

        with self.assertRaises(ValueError):
            adapter.execute(ActionCommand(ActionKind.KEY_DOWN, KeyboardTarget(("j",))))

        self.assertEqual([], client.calls)

    def test_adapter_uses_the_existing_virtual_gamepad_client_protocol(self):
        transport = JsonFileTransport()
        adapter = VirtualGamepadActionAdapter(
            device=VirtualGamepadClient(transport=transport),
            clock_ms=lambda: 20,
        )
        route = VirtualControllerRoute(controller=2, source="workbench", ttl_ms=240)

        adapter.execute(
            ActionCommand(
                ActionKind.GAMEPAD_TRIGGER,
                GamepadTriggerTarget(route, "lt", 96),
            )
        )

        self.assertEqual("set_trigger", transport.requests[0]["type"])
        self.assertEqual(
            {
                "source": "workbench",
                "trigger": "left",
                "value": 96,
                "controller": 2,
                "ttlMs": 240,
            },
            transport.requests[0]["payload"],
        )


if __name__ == "__main__":
    unittest.main()
