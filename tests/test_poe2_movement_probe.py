from tools.debug.poe2_movement_probe import run_bounded_output


class FakeOutput:
    def __init__(self):
        self.events = []

    def start(self):
        self.events.append("start")

    def write(self, vector, **kwargs):
        self.events.append(("write", vector))

    def stop(self):
        self.events.append("stop")


def test_probe_never_arms_when_another_window_is_foreground():
    output = FakeOutput()
    reason, ticks = run_bounded_output(
        output, game_pid=7, duration=0.1, current_foreground=lambda: 8
    )
    assert (reason, ticks) == ("game_not_foreground", 0)
    assert output.events == []


def test_probe_neutralizes_and_releases_on_focus_loss():
    output = FakeOutput()
    pids = iter((7, 7, 8))
    reason, ticks = run_bounded_output(
        output,
        game_pid=7,
        duration=0.2,
        current_foreground=lambda: next(pids),
        clock=lambda: 0.0,
        sleep=lambda _: None,
    )
    assert (reason, ticks) == ("focus_lost", 1)
    assert output.events == [
        "start",
        ("write", (1.0, 0.0)),
        ("write", (0.0, 0.0)),
        "stop",
    ]


def test_probe_holds_repeated_frames_for_bounded_duration():
    output = FakeOutput()
    current = [0.0]

    def sleep(seconds):
        current[0] += seconds

    reason, ticks = run_bounded_output(
        output,
        game_pid=7,
        duration=0.15,
        current_foreground=lambda: 7,
        clock=lambda: current[0],
        sleep=sleep,
    )
    assert (reason, ticks) == ("completed", 3)
    assert output.events[-2:] == [("write", (0.0, 0.0)), "stop"]
