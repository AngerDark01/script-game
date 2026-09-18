import unittest

from auto_modules.core.actions import ActionCommand, ActionKind, ActionRequest, MouseActionAdapter, PointerTarget
from auto_modules.core.perception.models import CoordinateSpace
from auto_modules.core.spatial import MappedPoint, Point2D


class _FakeMouseDevice:
    def __init__(self):
        self.calls = []

    def move_to(self, x, y):
        self.calls.append(("move", x, y))
        return True

    def mouse_down(self, button="left"):
        self.calls.append(("down", button))

    def mouse_up(self, button="left"):
        self.calls.append(("up", button))


class MouseActionAdapterTests(unittest.TestCase):
    def test_move_accepts_a_generic_pointer_command(self):
        device = _FakeMouseDevice()
        adapter = MouseActionAdapter(device=device, clock_ms=lambda: 1000, sleep=lambda _seconds: None)
        command = ActionCommand(
            kind=ActionKind.MOVE,
            target=PointerTarget(_mapped_point(480.4, 270.6)),
        )

        result = adapter.execute(command)

        self.assertEqual([("move", 480, 271)], device.calls)
        self.assertTrue(result.executed)
        self.assertEqual((480, 271), result.point)
        self.assertEqual(ActionKind.MOVE, result.kind)

    def test_double_click_moves_then_sends_two_left_down_up_pairs(self):
        device = _FakeMouseDevice()
        adapter = MouseActionAdapter(device=device, clock_ms=lambda: 1000, sleep=lambda _seconds: None)
        request = ActionRequest(
            kind=ActionKind.DOUBLE_CLICK,
            point=_mapped_point(480.4, 270.6),
            interval_ms=20,
        )

        result = adapter.execute(request)

        self.assertEqual(
            [
                ("move", 480, 271),
                ("down", "left"),
                ("up", "left"),
                ("down", "left"),
                ("up", "left"),
            ],
            device.calls,
        )
        self.assertTrue(result.executed)
        self.assertEqual((480, 271), result.point)
        self.assertEqual("mouse", result.device_id)
        self.assertEqual(ActionKind.DOUBLE_CLICK, result.kind)

    def test_click_moves_then_sends_one_left_down_up_pair(self):
        device = _FakeMouseDevice()
        adapter = MouseActionAdapter(device=device, clock_ms=lambda: 1000, sleep=lambda _seconds: None)

        result = adapter.execute(
            ActionCommand(
                kind=ActionKind.CLICK,
                target=PointerTarget(_mapped_point(100.4, 200.6)),
            )
        )

        self.assertEqual(1, result.metadata["click_count"])
        self.assertEqual(
            [("move", 100, 201), ("down", "left"), ("up", "left")],
            device.calls,
        )


def _mapped_point(x, y):
    return MappedPoint(
        source_point=Point2D(x, y),
        source_space=CoordinateSpace.FULL_SCREEN,
        destination_point=Point2D(x, y),
        destination_space=CoordinateSpace.PHYSICAL_SCREEN,
        metadata={"transform": "scale_offset"},
    )


if __name__ == "__main__":
    unittest.main()
