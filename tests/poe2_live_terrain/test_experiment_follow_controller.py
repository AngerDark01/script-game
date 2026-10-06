from auto_modules.features.poe2.live_terrain.experimental.follow import FollowController


class _Runtime:
    def __init__(self):
        self.refreshed = []

    def refresh_simulated_target(self, *, now_ms):
        self.refreshed.append(now_ms)

    def tick(self, *, now_ms):
        return {"tick": now_ms}


def test_follow_controller_only_ticks_when_started():
    runtime = _Runtime()
    controller = FollowController(runtime, target_source=object())
    assert controller.tick(now_ms=1) == {}
    controller.start()
    assert controller.tick(now_ms=2) == {"tick": 2}
    assert runtime.refreshed == [2]
    controller.stop()
    assert controller.tick(now_ms=3) == {}
