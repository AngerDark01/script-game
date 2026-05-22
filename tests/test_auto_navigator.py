import unittest

import numpy as np

from core.auto_navigator import AutoNavigator


class FakePathFinder:
    def __init__(self, path):
        self.path = list(path)
        self.calls = []

    def find_path(self, wall_map, start_pos, end_pos, explored_map=None):
        self.calls.append((start_pos, end_pos))
        return list(self.path)


class AutoNavigatorTest(unittest.TestCase):
    def test_next_target_uses_guide_route_before_later_required_point(self):
        navigator = AutoNavigator()
        route = {
            "exit_region": {"center": [100, 100], "radius": 20},
            "required_points": [[30, 30]],
            "guide_points": [[10, 10], [20, 20], [40, 40]],
        }
        navigator.load_route(route)
        self.assertEqual(navigator.current_segment_target_kind(), "guide")
        self.assertEqual(navigator.current_segment_target(), (10.0, 10.0))

    def test_next_target_prefers_required_point_when_it_is_before_next_guide(self):
        navigator = AutoNavigator()
        route = {
            "exit_region": {"center": [100, 100], "radius": 20},
            "required_points": [[5, 5]],
            "guide_points": [[10, 10], [20, 20]],
        }
        navigator.load_route(route)
        self.assertEqual(navigator.current_segment_target_kind(), "required")
        self.assertEqual(navigator.current_segment_target(), (5.0, 5.0))

    def test_next_target_prefers_first_guide_point(self):
        navigator = AutoNavigator()
        route = {
            "exit_region": {"center": [100, 100], "radius": 20},
            "guide_points": [[10, 10], [20, 20]],
        }
        navigator.load_route(route)
        self.assertEqual(navigator.current_segment_target(), (10.0, 10.0))

    def test_acquire_requires_consecutive_stable_positions(self):
        navigator = AutoNavigator()
        navigator.required_stable_frames = 3
        positions = [
            ((100, 100), 0.9),
            ((101, 100), 0.92),
            ((100, 101), 0.91),
        ]
        for pos, confidence in positions:
            navigator.observe_localization(pos, confidence)
        self.assertTrue(navigator.has_stable_lock())

    def test_click_cooldown_blocks_immediate_repeat(self):
        navigator = AutoNavigator()
        navigator.last_click_ms = 1000
        self.assertFalse(navigator.should_issue_click(now_ms=1200))
        self.assertTrue(navigator.should_issue_click(now_ms=1700))

    def test_configure_updates_click_cadence(self):
        navigator = AutoNavigator()
        navigator.configure(click_cooldown_ms=180, min_click_target_delta=3.5)
        self.assertEqual(navigator.click_cooldown_ms, 180)
        self.assertEqual(navigator.min_click_target_delta, 3.5)

    def test_default_direct_guidance_skips_pathfinder_obstacles(self):
        navigator = AutoNavigator()
        navigator.configure(prefer_direct_guidance=True)
        navigator.min_progress_delta = 9999
        navigator.progress_timeout_ms = 999999
        navigator.load_route({"exit_region": {"center": [80, 80], "radius": 10}, "guide_points": []})
        navigator.start()
        navigator.required_stable_frames = 1
        wall_map = np.zeros((128, 128), dtype=np.uint8)
        pathfinder = FakePathFinder([(10, 10), (10, 80), (80, 80)])

        plan_action = navigator.update(
            localized_pos=(10, 10),
            confidence=0.95,
            wall_map=wall_map,
            pathfinder=pathfinder,
            now_ms=1000,
            lookahead_distance=40,
        )

        self.assertEqual(plan_action["message"], "使用直线点击引导")
        self.assertEqual(pathfinder.calls, [])
        self.assertEqual(navigator.current_path, [(10.0, 10.0), (80.0, 80.0)])

    def test_default_planning_uses_pathfinder(self):
        navigator = AutoNavigator()
        navigator.min_progress_delta = 9999
        navigator.progress_timeout_ms = 999999
        navigator.load_route({"exit_region": {"center": [80, 80], "radius": 10}, "guide_points": []})
        navigator.start()
        navigator.required_stable_frames = 1
        wall_map = np.zeros((128, 128), dtype=np.uint8)
        pathfinder = FakePathFinder([(10, 10), (10, 80), (80, 80)])

        plan_action = navigator.update(
            localized_pos=(10, 10),
            confidence=0.95,
            wall_map=wall_map,
            pathfinder=pathfinder,
            now_ms=1000,
            lookahead_distance=40,
        )

        self.assertEqual(plan_action["message"], "路径规划完成")
        self.assertEqual(pathfinder.calls, [((10, 10), (80, 80))])
        self.assertEqual(navigator.current_path[0], (10.0, 10.0))
        self.assertEqual(navigator.current_path[-1], (80.0, 80.0))

    def test_route_alignment_skips_passed_guide_points(self):
        navigator = AutoNavigator()
        route = {
            "exit_region": {"center": [400, 0], "radius": 10},
            "guide_points": [[0, 0], [100, 0], [200, 0], [300, 0]],
        }
        navigator.load_route(route)
        navigator.start()
        navigator.required_stable_frames = 1
        wall_map = np.zeros((512, 512), dtype=np.uint8)
        pathfinder = FakePathFinder([(260, 10), (300, 0)])

        plan_action = navigator.update(
            localized_pos=(260, 10),
            confidence=0.95,
            wall_map=wall_map,
            pathfinder=pathfinder,
            now_ms=1000,
            lookahead_distance=40,
        )

        self.assertEqual(navigator.guide_index, 3)
        self.assertEqual(navigator.current_segment_target(), (300.0, 0.0))
        self.assertEqual(pathfinder.calls, [((260, 10), (300, 0))])
        self.assertIn("已按当前位置跳到路线点", plan_action["message"])

    def test_route_alignment_uses_nearest_marker_not_first_marker(self):
        navigator = AutoNavigator()
        route = {
            "exit_region": {"center": [400, 0], "radius": 10},
            "guide_points": [[0, 0], [100, 0], [200, 0], [300, 0]],
        }
        navigator.load_route(route)
        navigator.start()
        navigator.required_stable_frames = 1
        wall_map = np.zeros((512, 512), dtype=np.uint8)
        pathfinder = FakePathFinder([(205, 300), (200, 0)])

        navigator.update(
            localized_pos=(205, 300),
            confidence=0.95,
            wall_map=wall_map,
            pathfinder=pathfinder,
            now_ms=1000,
            lookahead_distance=40,
        )

        self.assertEqual(navigator.guide_index, 2)
        self.assertEqual(navigator.current_segment_target(), (200.0, 0.0))
        self.assertEqual(pathfinder.calls, [((205, 300), (200, 0))])

    def test_route_alignment_between_markers_targets_next_marker(self):
        navigator = AutoNavigator()
        route = {
            "exit_region": {"center": [400, 0], "radius": 10},
            "guide_points": [[0, 0], [100, 0], [200, 0], [300, 0]],
        }
        navigator.load_route(route)
        navigator.start()
        navigator.required_stable_frames = 1
        wall_map = np.zeros((512, 512), dtype=np.uint8)
        pathfinder = FakePathFinder([(40, 5), (100, 0)])

        navigator.update(
            localized_pos=(40, 5),
            confidence=0.95,
            wall_map=wall_map,
            pathfinder=pathfinder,
            now_ms=1000,
            lookahead_distance=40,
        )

        self.assertEqual(navigator.guide_index, 1)
        self.assertEqual(navigator.current_segment_target(), (100.0, 0.0))
        self.assertEqual(pathfinder.calls, [((40, 5), (100, 0))])

    def test_route_alignment_skips_marker_when_already_on_it(self):
        navigator = AutoNavigator()
        route = {
            "exit_region": {"center": [400, 0], "radius": 10},
            "guide_points": [[0, 0], [100, 0], [200, 0], [300, 0]],
        }
        navigator.load_route(route)
        navigator.start()
        navigator.required_stable_frames = 1
        wall_map = np.zeros((512, 512), dtype=np.uint8)
        pathfinder = FakePathFinder([(202, 2), (300, 0)])

        navigator.update(
            localized_pos=(202, 2),
            confidence=0.95,
            wall_map=wall_map,
            pathfinder=pathfinder,
            now_ms=1000,
            lookahead_distance=40,
        )

        self.assertEqual(navigator.guide_index, 3)
        self.assertEqual(navigator.current_segment_target(), (300.0, 0.0))
        self.assertEqual(pathfinder.calls, [((202, 2), (300, 0))])

    def test_route_alignment_keeps_pending_required_gate_but_allows_guide_before_it(self):
        navigator = AutoNavigator()
        route = {
            "exit_region": {"center": [400, 0], "radius": 10},
            "required_points": [[250, 0]],
            "guide_points": [[100, 0], [200, 0], [300, 0]],
        }
        navigator.load_route(route)
        navigator.start()
        navigator.required_stable_frames = 1
        wall_map = np.zeros((512, 512), dtype=np.uint8)
        pathfinder = FakePathFinder([(140, 5), (200, 0)])

        action = navigator.update(
            localized_pos=(140, 5),
            confidence=0.95,
            wall_map=wall_map,
            pathfinder=pathfinder,
            now_ms=1000,
            lookahead_distance=40,
        )

        self.assertEqual(navigator.required_index, 0)
        self.assertEqual(navigator.guide_index, 1)
        self.assertEqual(navigator.current_segment_target_kind(), "guide")
        self.assertEqual(navigator.current_segment_target(), (200.0, 0.0))
        self.assertEqual(pathfinder.calls, [((140, 5), (200, 0))])
        self.assertIn("已按当前位置跳到路线点", action["message"])

    def test_route_alignment_does_not_skip_guide_points_past_pending_required_gate(self):
        navigator = AutoNavigator()
        route = {
            "exit_region": {"center": [400, 0], "radius": 10},
            "required_points": [[250, 0]],
            "guide_points": [[100, 0], [200, 0], [300, 0]],
        }
        navigator.load_route(route)
        navigator.start()
        navigator.required_stable_frames = 1
        wall_map = np.zeros((512, 512), dtype=np.uint8)
        pathfinder = FakePathFinder([(260, 10), (250, 0)])

        action = navigator.update(
            localized_pos=(260, 10),
            confidence=0.95,
            wall_map=wall_map,
            pathfinder=pathfinder,
            now_ms=1000,
            lookahead_distance=40,
        )

        self.assertEqual(navigator.required_index, 0)
        self.assertEqual(navigator.guide_index, 2)
        self.assertEqual(navigator.current_segment_target_kind(), "required")
        self.assertEqual(navigator.current_segment_target(), (250.0, 0.0))
        self.assertEqual(pathfinder.calls, [((260, 10), (250, 0))])
        self.assertIn("已按当前位置跳到路线点", action["message"])

    def test_required_points_advance_in_order_without_repeating(self):
        navigator = AutoNavigator()
        navigator.min_progress_delta = 9999
        navigator.progress_timeout_ms = 999999
        route = {
            "exit_region": {"center": [200, 0], "radius": 10},
            "required_points": [[50, 0], [100, 0]],
            "guide_points": [],
        }
        navigator.load_route(route)
        navigator.start()
        navigator.required_stable_frames = 1
        wall_map = np.zeros((256, 256), dtype=np.uint8)
        pathfinder = FakePathFinder([(0, 0), (50, 0)])

        navigator.update(
            localized_pos=(0, 0),
            confidence=0.95,
            wall_map=wall_map,
            pathfinder=pathfinder,
            now_ms=1000,
            lookahead_distance=40,
        )
        navigator.update(
            localized_pos=(50, 0),
            confidence=0.95,
            wall_map=wall_map,
            pathfinder=pathfinder,
            now_ms=1100,
            lookahead_distance=40,
        )
        action = navigator.update(
            localized_pos=(50, 0),
            confidence=0.95,
            wall_map=wall_map,
            pathfinder=pathfinder,
            now_ms=1200,
            lookahead_distance=40,
        )

        self.assertEqual(action["message"], "必经点已到达，规划下一个必经点")
        self.assertEqual(navigator.required_index, 1)
        self.assertEqual(navigator.current_segment_target_kind(), "required")
        self.assertEqual(navigator.current_segment_target(), (100.0, 0.0))

    def test_reaching_guide_does_not_advance_required_index(self):
        navigator = AutoNavigator()
        navigator.min_progress_delta = 9999
        navigator.progress_timeout_ms = 999999
        route = {
            "exit_region": {"center": [200, 0], "radius": 10},
            "required_points": [[120, 0]],
            "guide_points": [[50, 0], [100, 0]],
        }
        navigator.load_route(route)
        navigator.start()
        navigator.required_stable_frames = 1
        wall_map = np.zeros((256, 256), dtype=np.uint8)
        pathfinder = FakePathFinder([(0, 0), (50, 0)])

        navigator.update(
            localized_pos=(0, 0),
            confidence=0.95,
            wall_map=wall_map,
            pathfinder=pathfinder,
            now_ms=1000,
            lookahead_distance=40,
        )
        navigator.update(
            localized_pos=(50, 0),
            confidence=0.95,
            wall_map=wall_map,
            pathfinder=pathfinder,
            now_ms=1100,
            lookahead_distance=40,
        )
        action = navigator.update(
            localized_pos=(50, 0),
            confidence=0.95,
            wall_map=wall_map,
            pathfinder=pathfinder,
            now_ms=1200,
            lookahead_distance=40,
        )

        self.assertEqual(action["message"], "途经点已到达，规划下一段")
        self.assertEqual(navigator.required_index, 0)
        self.assertEqual(navigator.guide_index, 1)
        self.assertEqual(navigator.current_segment_target_kind(), "guide")
        self.assertEqual(navigator.current_segment_target(), (100.0, 0.0))

    def test_guide_alignment_resumes_after_all_required_points_complete(self):
        navigator = AutoNavigator()
        route = {
            "exit_region": {"center": [400, 0], "radius": 10},
            "required_points": [[100, 0]],
            "guide_points": [[200, 0], [300, 0]],
        }
        navigator.load_route(route)
        navigator.required_index = 1
        navigator.active = True
        navigator.state = "PLAN_SEGMENT"
        navigator.required_stable_frames = 1
        wall_map = np.zeros((512, 512), dtype=np.uint8)
        pathfinder = FakePathFinder([(260, 10), (300, 0)])

        navigator.update(
            localized_pos=(260, 10),
            confidence=0.95,
            wall_map=wall_map,
            pathfinder=pathfinder,
            now_ms=1000,
            lookahead_distance=40,
        )

        self.assertEqual(navigator.guide_index, 1)
        self.assertEqual(navigator.current_segment_target(), (300.0, 0.0))
        self.assertEqual(pathfinder.calls, [((260, 10), (300, 0))])

    def test_stuck_detected_when_progress_does_not_increase(self):
        navigator = AutoNavigator()
        navigator.min_progress_delta = 8
        navigator.progress_timeout_ms = 1000
        navigator.last_progress_value = 100
        navigator.last_progress_ms = 1000
        self.assertTrue(navigator.is_stuck(current_progress=103, now_ms=2200))
        self.assertFalse(navigator.is_stuck(current_progress=120, now_ms=2200))

    def test_update_emits_single_click_then_holds_during_cooldown(self):
        navigator = AutoNavigator()
        navigator.click_cooldown_ms = 500
        navigator.min_progress_delta = 9999
        navigator.progress_timeout_ms = 999999
        navigator.load_route({"exit_region": {"center": [80, 80], "radius": 10}, "guide_points": []})
        navigator.start()
        navigator.required_stable_frames = 1
        wall_map = np.zeros((128, 128), dtype=np.uint8)
        pathfinder = FakePathFinder([(10, 10), (80, 80)])

        plan_action = navigator.update(
            localized_pos=(10, 10),
            confidence=0.95,
            wall_map=wall_map,
            pathfinder=pathfinder,
            now_ms=1000,
            lookahead_distance=40,
        )
        self.assertEqual(plan_action["type"], "status")
        self.assertEqual(plan_action["state"], "FOLLOW_SEGMENT")

        move_action = navigator.update(
            localized_pos=(10, 10),
            confidence=0.95,
            wall_map=wall_map,
            pathfinder=pathfinder,
            now_ms=1100,
            lookahead_distance=40,
        )
        self.assertEqual(move_action["type"], "move")
        self.assertTrue(move_action["issued_click"])
        self.assertIsNotNone(move_action["target_pos"])

        hold_action = navigator.update(
            localized_pos=(10, 10),
            confidence=0.95,
            wall_map=wall_map,
            pathfinder=pathfinder,
            now_ms=1300,
            lookahead_distance=40,
        )
        self.assertEqual(hold_action["type"], "move")
        self.assertFalse(hold_action["issued_click"])
        self.assertEqual(hold_action["message"], "保持当前移动")
        self.assertIsNotNone(hold_action["target_pos"])

    def test_pathfinder_failure_falls_back_to_direct_guidance(self):
        navigator = AutoNavigator()
        navigator.configure(prefer_direct_guidance=False)
        navigator.direct_fallback_distance = 30
        navigator.click_cooldown_ms = 500
        navigator.min_progress_delta = 9999
        navigator.progress_timeout_ms = 999999
        navigator.load_route({"exit_region": {"center": [80, 80], "radius": 10}, "guide_points": []})
        navigator.start()
        navigator.required_stable_frames = 1
        wall_map = np.zeros((128, 128), dtype=np.uint8)
        pathfinder = FakePathFinder([])

        plan_action = navigator.update(
            localized_pos=(10, 10),
            confidence=0.95,
            wall_map=wall_map,
            pathfinder=pathfinder,
            now_ms=1000,
            lookahead_distance=40,
        )
        self.assertEqual(plan_action["type"], "status")
        self.assertEqual(plan_action["state"], "FOLLOW_SEGMENT")
        self.assertEqual(plan_action["message"], "A*失败，改用局部脱困点")
        self.assertEqual(plan_action["path_kind"], "local_fallback")
        self.assertEqual(navigator.current_path[0], (10.0, 10.0))
        self.assertNotEqual(navigator.current_path[-1], (80.0, 80.0))
        self.assertLess(
            ((navigator.current_path[-1][0] - 10.0) ** 2 + (navigator.current_path[-1][1] - 10.0) ** 2) ** 0.5,
            ((80.0 - 10.0) ** 2 + (80.0 - 10.0) ** 2) ** 0.5,
        )
        self.assertTrue(navigator.active)

        move_action = navigator.update(
            localized_pos=(10, 10),
            confidence=0.95,
            wall_map=wall_map,
            pathfinder=pathfinder,
            now_ms=1100,
            lookahead_distance=40,
        )
        self.assertEqual(move_action["type"], "move")
        self.assertTrue(move_action["issued_click"])
        self.assertIsNotNone(move_action["target_pos"])

        replan_action = navigator.update(
            localized_pos=navigator.current_path[-1],
            confidence=0.95,
            wall_map=wall_map,
            pathfinder=pathfinder,
            now_ms=1700,
            lookahead_distance=40,
        )
        self.assertEqual(replan_action["message"], "临时脱困点已到达，重新规划")
        self.assertEqual(replan_action["state"], "PLAN_SEGMENT")

    def test_recover_click_marks_issued_click(self):
        navigator = AutoNavigator()
        navigator.load_route({"exit_region": {"center": [80, 80], "radius": 10}, "guide_points": []})
        navigator.current_path = [(10.0, 10.0), (80.0, 80.0)]
        navigator.current_path_lengths = [0.0, ((70.0 ** 2 + 70.0 ** 2) ** 0.5)]
        navigator.control_pos = (10.0, 10.0)
        navigator.current_target = (80.0, 80.0)
        navigator.state = "STUCK_RECOVER"
        navigator.active = True

        action = navigator.update(
            localized_pos=(10, 10),
            confidence=0.95,
            wall_map=np.zeros((128, 128), dtype=np.uint8),
            pathfinder=FakePathFinder([(10, 10), (80, 80)]),
            now_ms=2000,
            lookahead_distance=40,
        )

        self.assertEqual(action["type"], "move")
        self.assertTrue(action["issued_click"])
        self.assertEqual(action["message"], "执行绕障试探点击")


if __name__ == "__main__":
    unittest.main()
