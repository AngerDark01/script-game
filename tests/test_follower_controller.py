import numpy as np
from dataclasses import replace
from auto_modules.core.lan_follow import SharedPosition
from auto_modules.application.follow.controller import FollowerController


def position(actor, xy, stamp=100):
    return SharedPosition('pc', actor, 'map', 'v1', xy, .9, stamp, 's1')


def test_dual_controllers_keep_independent_paths_and_stop_on_stale_or_wrong_map():
    walls = np.zeros((100, 100), np.uint8)
    a = FollowerController(walls, actor_id='A1', map_id='map', map_version='v1', downsample_factor=1)
    b = FollowerController(walls, actor_id='A2', map_id='map', map_version='v1', downsample_factor=1)
    leader = position('B', (80, 40))
    one = a.tick(position('A1', (10, 40)), leader, now_ms=110)
    two = b.tick(position('A2', (80, 80)), leader, now_ms=110)
    assert one.vector[0] > 0 and two.vector[1] < 0
    assert one.path != two.path
    assert a.tick(position('A1', (10, 40)), leader, now_ms=351).vector == (0., 0.)
    assert b.tick(position('A2', (80, 80)), replace(leader, map_version='v2'), now_ms=120).vector == (0., 0.)


def test_stuck_goes_neutral_then_safe_escape_and_expires_without_new_positions():
    a = FollowerController(np.zeros((100,100),np.uint8), actor_id='A1', map_id='map', map_version='v1', downsample_factor=1)
    for stamp in (0, 20, 120, 220, 320):
        result = a.tick(position('A1', (30,40),stamp), position('B',(80,40),stamp),now_ms=stamp)
    result = a.tick(position('A1',(30,40),430),position('B',(80,40),430),now_ms=430)
    assert result.state == 'recover_neutral' and result.vector == (0.,0.)
    result = a.tick(position('A1',(30,40),450),position('B',(80,40),450),now_ms=450)
    assert result.state == 'recovering' and result.vector != (0.,0.)
    assert a.tick(position('A1',(30,40),450),position('B',(80,40),450),now_ms=800).vector == (0.,0.)
