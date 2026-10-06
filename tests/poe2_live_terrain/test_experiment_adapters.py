from auto_modules.features.poe2.live_terrain.experimental.adapters import (
    RecordingGamepad,
    StaticMemory,
    StaticWindow,
)


def test_fakes_are_deterministic_and_have_no_device_side_effects():
    memory = StaticMemory((("p1", (1, 2)),))
    assert memory.read_player_positions() == (("p1", (1, 2)),)
    assert memory.read_count == 1
    window = StaticWindow(False)
    assert window.is_game_foreground() is False
    gamepad = RecordingGamepad()
    assert gamepad.acquire(2) is gamepad
    gamepad.submit(2, (100, -100))
    assert gamepad.commands == [(2, (100, -100))]
