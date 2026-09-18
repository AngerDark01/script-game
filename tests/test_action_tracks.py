from auto_modules.core.events.action_tracks import ActionTrack, TrackMode


def test_parallel_single_and_continuous_tracks():
    tracks = [
        ActionTrack(('A',), mode=TrackMode.CONTINUOUS, hold_ms=100, interval_ms=300),
        ActionTrack(('LB', 'X'), mode=TrackMode.ONCE, hold_ms=50),
    ]
    assert ActionTrack.buttons_at(tracks, 0) == {'A', 'LB', 'X'}
    assert ActionTrack.buttons_at(tracks, 49) == {'A', 'LB', 'X'}
    assert ActionTrack.buttons_at(tracks, 50) == {'A'}
    assert ActionTrack.buttons_at(tracks, 100) == set()
    assert ActionTrack.buttons_at(tracks, 300) == {'A'}


def test_frequency_skips_missed_periods_without_burst():
    track = ActionTrack(('A',), mode=TrackMode.FREQUENCY, hold_ms=40, interval_ms=100)
    assert track.active_at(0)
    assert track.active_at(39)
    assert not track.active_at(40)
    assert track.active_at(100)
    assert not track.active_at(250)  # polling late does not replay 200 immediately
    assert track.active_at(300)
