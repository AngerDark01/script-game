import numpy as np

from auto_modules.features.poe2.live_terrain.experimental.multiplayer_follow.target_projection import WalkableTargetProjector


def test_target_on_wall_projects_to_nearest_walkable_cell():
    walls = np.zeros((9, 9), dtype=np.uint8)
    walls[4, 4] = 255
    result = WalkableTargetProjector(walls, radius=3).project((4, 4))
    assert result.projected
    assert result.position != (4.0, 4.0)
    assert walls[int(result.position[1]), int(result.position[0])] == 0


def test_walkable_target_is_preserved():
    walls = np.zeros((9, 9), dtype=np.uint8)
    result = WalkableTargetProjector(walls).project((2.25, 3.75))
    assert not result.projected
    assert result.position == (2.25, 3.75)
    assert result.diagnostics["status"] == "target_walkable"


def test_projection_prefers_open_neighbor_and_reports_quantized_status():
    walls = np.zeros((11, 11), dtype=np.uint8)
    walls[5, 5] = 255
    walls[4:7, 4] = 255
    walls[4:7, 6] = 255
    result = WalkableTargetProjector(walls, radius=3).project((5, 5))
    assert result.projected
    assert result.diagnostics["status"] == "target_projected"
    assert result.diagnostics["clearance"] >= 0.0
    assert "score" in result.diagnostics
