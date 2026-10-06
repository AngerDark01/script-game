from auto_modules.features.poe2.live_terrain.experimental.multiplayer import (
    DualMotionController,
    DualMotionFrameRouter,
)


def test_router_rejects_retired_worker_frame():
    router = DualMotionFrameRouter()
    router.begin(2)
    assert router.accept(1, object()) is None
    event = router.accept(2, {"frame": 1})
    assert event is not None
    assert event.kind == "frame_ready"
    assert router.accepted_frames == 1


def test_controller_lifecycle_is_headless():
    controller = DualMotionController()
    assert controller.start(3).kind == "started"
    assert controller.running is True
    assert controller.publish(3, "frame").payload == "frame"
    assert controller.stop().kind == "stopped"
