import unittest

from core.actions import ActionResult
from gui.modes.navigation.hooks.registration import NavigationHookRuntime


class _MotionController:
    def __init__(self):
        self.calls = []

    def set_control_enabled(self, enabled):
        self.calls.append(("enabled", enabled))


class _ActionAdapter:
    def __init__(self):
        self.calls = []

    def execute(self, command, *, reason=None):
        self.calls.append((command, reason))
        return ActionResult(
            executed=True,
            device_id="fake",
            kind=command.kind,
            started_at_ms=1,
            completed_at_ms=2,
            target=command.target,
        )


class NavigationHookActionTests(unittest.TestCase):
    def test_key_hook_uses_the_common_primitive_action_adapter(self):
        motion = _MotionController()
        adapter = _ActionAdapter()
        enabled = []
        runtime = NavigationHookRuntime(
            navigation_task_controller=object(),
            motion_controller=motion,
            enable_game_input_mode=lambda: enabled.append(True),
            action_adapter=adapter,
        )

        result = runtime._press_key_once("D", "hook:portal")

        self.assertTrue(result.executed)
        self.assertEqual([True], enabled)
        self.assertEqual([("enabled", True)], motion.calls)
        self.assertEqual(("d",), adapter.calls[0][0].target.keys)
        self.assertEqual("hook:portal", adapter.calls[0][1])


if __name__ == "__main__":
    unittest.main()
