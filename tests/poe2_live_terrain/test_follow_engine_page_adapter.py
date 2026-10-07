from __future__ import annotations

from auto_modules.features.poe2.live_terrain.experimental.follow_engine.engine import FollowEnginePort, FollowEngineStart
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.ui_adapter import FollowEngineUiAdapter
from auto_modules.ui.modes.poe2_live_terrain.follow_engine_adapter import Poe2FollowEnginePageAdapter


class _Fake:
    def __init__(self):
        self.targets = []
        self.active = False

    def start(self, **_kwargs):
        self.active = True

    def poll_latest(self):
        return None

    def send_visual(self, _observation):
        pass

    def update_target(self, role_id, target):
        self.targets.append((role_id, target))

    def stop(self, **_kwargs):
        self.active = False


class _Output:
    def start(self):
        pass

    def apply(self, _snapshot):
        pass

    def stop(self, **_kwargs):
        pass


def test_page_adapter_only_translates_events_and_publishes_state():
    vision = _Fake()
    control = _Fake()
    page = Poe2FollowEnginePageAdapter(
        FollowEngineUiAdapter(FollowEnginePort(vision=vision, control=control, output=_Output()))
    )
    page.start(FollowEngineStart("map-a", {"p2": 2}))
    page.target_clicked("p2", (3.0, 4.0))
    assert control.targets == [("p2", (3.0, 4.0))]
    assert page.poll().active is True
    page.stop()
    assert page.poll().active is False
