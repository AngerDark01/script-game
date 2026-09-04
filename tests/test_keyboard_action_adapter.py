import unittest

from core.actions import (
    ActionCommand,
    ActionKind,
    KeyboardActionAdapter,
    KeyboardTarget,
    PointerTarget,
)
from core.perception.models import CoordinateSpace
from core.spatial import MappedPoint, Point2D


class _FakeKeyboardDevice:
    def __init__(self):
        self.calls = []

    def key_down(self, key):
        self.calls.append(("down", key))

    def key_up(self, key):
        self.calls.append(("up", key))


class KeyboardActionAdapterTests(unittest.TestCase):
    def test_key_chord_presses_in_order_and_releases_in_reverse_order(self):
        device = _FakeKeyboardDevice()
        adapter = KeyboardActionAdapter(device=device, clock_ms=lambda: 10)
        command = ActionCommand(ActionKind.KEY_CHORD, KeyboardTarget(("ctrl", "shift", "p")))

        result = adapter.execute(command)

        self.assertEqual(
            [
                ("down", "ctrl"),
                ("down", "shift"),
                ("down", "p"),
                ("up", "p"),
                ("up", "shift"),
                ("up", "ctrl"),
            ],
            device.calls,
        )
        self.assertTrue(result.executed)
        self.assertEqual("keyboard", result.device_id)
        self.assertIsNone(result.point)

    def test_key_down_and_key_up_are_independent_commands(self):
        device = _FakeKeyboardDevice()
        adapter = KeyboardActionAdapter(device=device, clock_ms=lambda: 10)

        adapter.execute(ActionCommand(ActionKind.KEY_DOWN, KeyboardTarget(("j",))))
        adapter.execute(ActionCommand(ActionKind.KEY_UP, KeyboardTarget(("j",))))

        self.assertEqual([("down", "j"), ("up", "j")], device.calls)

    def test_pointer_command_is_rejected_before_keyboard_device_io(self):
        device = _FakeKeyboardDevice()
        adapter = KeyboardActionAdapter(device=device, clock_ms=lambda: 10)
        pointer = PointerTarget(_mapped_point(10, 10))

        with self.assertRaises(ValueError):
            adapter.execute(ActionCommand(ActionKind.MOVE, pointer))

        self.assertEqual([], device.calls)


def _mapped_point(x, y):
    return MappedPoint(
        source_point=Point2D(x, y),
        source_space=CoordinateSpace.FULL_SCREEN,
        destination_point=Point2D(x, y),
        destination_space=CoordinateSpace.PHYSICAL_SCREEN,
        metadata={},
    )


if __name__ == "__main__":
    unittest.main()
