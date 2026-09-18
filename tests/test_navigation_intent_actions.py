import unittest

from auto_modules.core.actions import ActionCommand, ActionKind, ActionResult, KeyboardTarget, PointerTarget
from auto_modules.core.navigation_tasks.models import NavigationIntent, NavigationIntentType
from auto_modules.ui.modes.navigation.input.actions import (
    MapMovementAction,
    PrimitiveNavigationAction,
    translate_navigation_intent,
)
from auto_modules.ui.modes.navigation.input.intent_executor import execute_navigation_intent


class _MotionController:
    def __init__(self):
        self.calls = []

    def set_control_enabled(self, enabled):
        self.calls.append(("enabled", enabled))

    def move_to_map_target(self, player_pos, subgoal):
        self.calls.append(("move", player_pos, subgoal))
        return {"screen_radius": 100.0, "raw_screen_radius": 120.0}

    def click_map_target_once(self, player_pos, subgoal, *, reason):
        self.calls.append(("force", player_pos, subgoal, reason))
        return {"screen_radius": 90.0, "raw_screen_radius": 95.0}


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


class _TaskController:
    def __init__(self):
        self.calls = []

    def record_intent_click(self, intent, now_ms):
        self.calls.append((intent, now_ms))


class NavigationIntentActionTests(unittest.TestCase):
    def test_screen_click_translation_declares_an_explicit_physical_pointer_command(self):
        action = translate_navigation_intent(
            NavigationIntent(
                type=NavigationIntentType.CLICK_SCREEN,
                message="interact",
                metadata={"screen_pos": (120.4, 80.6)},
            )
        )

        self.assertIsInstance(action, PrimitiveNavigationAction)
        self.assertEqual("interact", action.reason)
        self.assertEqual(ActionKind.CLICK, action.command.kind)
        self.assertIsInstance(action.command.target, PointerTarget)
        self.assertEqual((120.4, 80.6), (
            action.command.target.point.destination_point.x,
            action.command.target.point.destination_point.y,
        ))

    def test_key_translation_builds_one_key_chord(self):
        action = translate_navigation_intent(
            NavigationIntent(
                type=NavigationIntentType.PRESS_KEY,
                message="loot",
                metadata={"key": "A"},
            )
        )

        self.assertIsInstance(action, PrimitiveNavigationAction)
        self.assertEqual(ActionKind.KEY_CHORD, action.command.kind)
        self.assertEqual(("a",), action.command.target.keys)

    def test_map_translation_never_becomes_a_pointer_command(self):
        action = translate_navigation_intent(
            NavigationIntent(
                type=NavigationIntentType.MOVE_MAP,
                player_pos=(10.0, 20.0),
                subgoal=(30.0, 40.0),
                metadata={"force_click_target": True},
            )
        )

        self.assertIsInstance(action, MapMovementAction)
        self.assertTrue(action.force_click_target)

    def test_executor_uses_primitive_adapter_for_key_without_direct_motion_key_call(self):
        motion = _MotionController()
        adapter = _ActionAdapter()
        tasks = _TaskController()
        enabled = []
        intent = NavigationIntent(
            type=NavigationIntentType.PRESS_KEY,
            message="portal interaction",
            metadata={"key": "d"},
        )

        result = execute_navigation_intent(
            intent,
            123,
            motion_controller=motion,
            navigation_task_controller=tasks,
            enable_game_input_mode=lambda: enabled.append(True),
            action_adapter=adapter,
        )

        self.assertTrue(result.handled)
        self.assertEqual([True], enabled)
        self.assertEqual([], motion.calls)
        self.assertEqual(ActionKind.KEY_CHORD, adapter.calls[0][0].kind)
        self.assertEqual("portal interaction", adapter.calls[0][1])

    def test_executor_retains_forced_map_click_and_records_same_intent(self):
        motion = _MotionController()
        adapter = _ActionAdapter()
        tasks = _TaskController()
        intent = NavigationIntent(
            type=NavigationIntentType.MOVE_MAP,
            player_pos=(10.0, 20.0),
            subgoal=(30.0, 40.0),
            message="force portal point",
            metadata={"force_click_target": True},
        )

        result = execute_navigation_intent(
            intent,
            456,
            motion_controller=motion,
            navigation_task_controller=tasks,
            enable_game_input_mode=lambda: None,
            action_adapter=adapter,
        )

        self.assertTrue(result.handled)
        self.assertEqual(
            [("enabled", True), ("force", (10.0, 20.0), (30.0, 40.0), "force portal point")],
            motion.calls,
        )
        self.assertEqual([(intent, 456)], tasks.calls)
        self.assertEqual([], adapter.calls)


if __name__ == "__main__":
    unittest.main()
