from virtual_gamepad_ui.main import requires_elevation


def test_regular_ui_requires_elevation_only_when_needed():
    assert requires_elevation(is_windows=True, is_admin=False, demo=False)
    assert not requires_elevation(is_windows=True, is_admin=True, demo=False)
    assert not requires_elevation(is_windows=False, is_admin=False, demo=False)


def test_demo_never_requests_elevation():
    assert not requires_elevation(is_windows=True, is_admin=False, demo=True)
