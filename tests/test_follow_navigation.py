import numpy as np
from core.routing.follow_target import FollowTargetGenerator
from core.routing.follower_planner import FollowerPlanner
from core.routing.vector_tracker import VectorPathTracker
from core.routing.stuck_recovery import ProgressWatchdog


def test_target_follows_leader_trail_instead_of_cutting_corner():
    generator = FollowTargetGenerator()
    for i, point in enumerate(((10, 10), (20, 10), (20, 20))):
        generator.observe(point, i*100)
    assert generator.target(15) == (15, 10)
    assert not generator.observe((999, 999), 100)


def test_existing_astar_avoids_walls_and_caches_independently():
    walls = np.zeros((60, 60), np.uint8)
    walls[5:55, 30] = 255
    p1 = FollowerPlanner(walls, downsample_factor=1)
    p2 = FollowerPlanner(walls, downsample_factor=1)
    path = p1.plan((10, 20), (50, 20))
    assert path
    assert p1.plan((10, 21), (50, 20)) == path
    assert p1.replans == 1
    assert p2.replans == 0
    assert p1.plan((10, 20), (30, 20)) == ()


def test_vector_tracker_stops_at_target_and_never_cuts_wall():
    walls = np.zeros((60, 60), np.uint8)
    tracker = VectorPathTracker(lookahead=10, arrival_radius=2)
    motion = tracker.command((5, 5), [(5, 5), (40, 5)], walls=walls)
    assert motion[0] > 0 and motion[1] == 0
    assert tracker.command((40, 5), [(5, 5), (40, 5)], walls=walls) == (0., 0.)
    walls[:, 15] = 255
    assert tracker.command((5, 5), [(5, 5), (40, 5)], walls=walls) == (0., 0.)


def test_stuck_requires_fresh_elapsed_progress_and_resets_on_pause():
    progress = ProgressWatchdog(timeout_ms=400, minimum_progress=2)
    assert not progress.update((10, 10), now_ms=0, moving=True)
    assert progress.update((10, 10), now_ms=401, moving=True)
    progress.reset()
    assert not progress.update((10, 10), now_ms=500, moving=False)
    assert not progress.update((10, 10), now_ms=1000, moving=True)
