from auto_modules.core.localization.map_localizer import LocalizationMode, MapLocalizer


def test_first_frame_uses_global_matcher():
    calls = []
    localizer = MapLocalizer(
        global_match=lambda frame: calls.append("global") or ((100.0, 80.0), 0.9),
        local_match=lambda frame, origin: calls.append("local") or ((101.0, 81.0), 0.8),
        phase_predict=lambda previous, current: None,
    )
    result = localizer.update("frame-1")
    assert result.position == (100.0, 80.0)
    assert result.source == "global"
    assert calls == ["global"]
    assert localizer.mode is LocalizationMode.LOCAL_TRACKING


def test_local_failure_requires_global_recovery_on_next_frame():
    calls = []
    localizer = MapLocalizer(
        global_match=lambda frame: calls.append("global") or ((100.0, 80.0), 0.9),
        local_match=lambda frame, origin: calls.append("local") or None,
        phase_predict=lambda previous, current: (101.0, 80.0),
    )
    localizer.update("frame-1")
    failed = localizer.update("frame-2")
    assert failed.position is None
    assert failed.source == "failed"
    assert calls == ["global", "local"]
    assert localizer.mode is LocalizationMode.RECOVERY_REQUIRED
    recovered = localizer.update("frame-3")
    assert recovered.source == "global"
    assert calls == ["global", "local", "global"]
