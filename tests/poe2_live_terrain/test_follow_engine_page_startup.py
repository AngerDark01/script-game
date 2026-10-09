"""Page startup contract tests without constructing Qt widgets or real outputs."""
from types import SimpleNamespace
import logging

import pytest

from auto_modules.ui.modes.poe2_live_terrain.capture_test_page import Poe2CaptureTestPage


def test_modular_countdown_is_not_hidden_by_control_snapshot(monkeypatch):
    now = [100.0]
    monkeypatch.setattr("auto_modules.ui.modes.poe2_live_terrain.capture_test_page.time.monotonic", lambda: now[0])
    messages = []
    state = SimpleNamespace(active=True, diagnostics={}, snapshot=SimpleNamespace(recovery_state="tracking", recovery_reason="visual"))
    page = SimpleNamespace(
        _follow_engine_page_adapter=SimpleNamespace(poll=lambda: state),
        _modular_follow_active=True,
        _modular_follow_arm_deadline=110.0,
        follow_status_label=SimpleNamespace(setText=messages.append),
        _logger=logging.getLogger("countdown_test"),
        _render_modular_follow_frame=lambda _frame: None,
        _render_modular_follow_map=lambda _snapshot: None,
    )
    Poe2CaptureTestPage._poll_modular_follow_engine(page)
    assert "10秒后允许移动" in messages[-1]
    now[0] = 109.0
    Poe2CaptureTestPage._poll_modular_follow_engine(page)
    assert "1秒后允许移动" in messages[-1]
    now[0] = 110.0
    Poe2CaptureTestPage._poll_modular_follow_engine(page)
    assert "tracking" in messages[-1]
    state.diagnostics = {"last_error": "worker_stall:vision", "worker_state": {"vision": "stalled"}}
    Poe2CaptureTestPage._poll_modular_follow_engine(page)
    assert "等待恢复" in messages[-1]


def test_preview_failure_does_not_hide_countdown_or_poll_diagnostics(monkeypatch, caplog):
    monkeypatch.setattr("auto_modules.ui.modes.poe2_live_terrain.capture_test_page.time.monotonic", lambda: 100.0)
    def broken_preview(_frame):
        raise ValueError("bad preview payload")
    messages, maps = [], []
    state = SimpleNamespace(active=True, diagnostics={"last_parent_event": {"vision": 17, "control": 23}}, snapshot=None)
    page = SimpleNamespace(
        _follow_engine_page_adapter=SimpleNamespace(poll=lambda: state),
        _modular_follow_active=True, _modular_follow_arm_deadline=110.0,
        follow_status_label=SimpleNamespace(setText=messages.append),
        _logger=logging.getLogger("preview_test"),
        _render_modular_follow_frame=broken_preview,
        _render_modular_follow_map=maps.append,
    )
    with caplog.at_level(logging.INFO):
        Poe2CaptureTestPage._poll_modular_follow_engine(page)
    assert "10秒后允许移动" in messages[-1]
    assert maps == [None]
    assert "vision_seq=17 control_tick=23" in caplog.text
    assert "preview_render_failed" in caplog.text
    assert "modular_poll_failed" not in caplog.text


@pytest.mark.parametrize("mode,expected", [
    ("p1_leads", {"role-b": 2}),
    ("p2_leads", {"role-a": 1}),
    ("single_p1_program", {"role-a": 1}),
    ("single_p2_program", {"role-b": 2}),
    ("both_program", {"role-a": 1, "role-b": 2}),
])
def test_modular_selected_output_roles_match_follow_target_roles(mode, expected):
    combo = lambda value: SimpleNamespace(currentData=lambda: value)
    page = SimpleNamespace(
        follow_mode_combo=combo(mode), follow_p1_combo=combo("role-a"),
        follow_p2_combo=combo("role-b"),
    )
    roles = Poe2CaptureTestPage._modular_follow_roles(page)
    assert roles == expected
    assert set(roles) == set(Poe2CaptureTestPage._modular_follow_target_roles(page))


def test_failed_owned_adapter_start_disposes_composition_and_can_be_rebuilt():
    stops = []

    def fail_start(_config):
        raise RuntimeError("spawn serialization failed")

    adapter = SimpleNamespace(start=fail_start, stop=lambda **kw: stops.append(("adapter", kw)))
    composition = SimpleNamespace(stop=lambda **kw: stops.append(("composition", kw)))
    page = SimpleNamespace(
        _modular_follow_roles=lambda: {"role-b": 2},
        _ensure_modular_follow_adapter=lambda _roles: True,
        _follow_engine_page_adapter=adapter, _follow_engine_composition=composition,
        _follow_engine_adapter_owned=True, _follow_runtime=None, _follow_program_output=None,
        _snapshot=SimpleNamespace(metadata=SimpleNamespace(instance_id="map-a")),
        _dual_map_transform=object(), _dual_follow_reference=object(), _dual_motion_worker=None,
        _dual_motion_timer=SimpleNamespace(isActive=lambda: False),
        _modular_follow_policy=lambda: ("role-a", ("role-b",)),
        _logger=logging.getLogger("page_start_test"),
        follow_status_label=SimpleNamespace(setText=lambda _text: None),
        _modular_follow_active=False,
    )
    assert not Poe2CaptureTestPage._start_modular_follow_experiment(page)
    assert [item[0] for item in stops] == ["adapter", "composition"]
    assert page._follow_engine_page_adapter is None
    assert page._follow_engine_composition is None
    assert page._follow_engine_adapter_owned is False
    assert page._modular_follow_live_mode is False


def test_async_failed_owned_adapter_clears_references_before_retry():
    class Button:
        def setEnabled(self, _value):
            pass

    class Label:
        def setText(self, _value):
            pass

    page = SimpleNamespace(
        _follow_lifecycle_serial=1,
        _modular_follow_start_pending=True,
        _modular_follow_stop_pending=False,
        _modular_follow_active=True,
        _modular_follow_live_mode=True,
        _follow_engine_adapter_owned=True,
        _follow_engine_page_adapter=object(),
        _follow_engine_composition=object(),
        _follow_timer=SimpleNamespace(stop=lambda: None, setInterval=lambda _value: None),
        _follow_timer_default_interval=100,
        start_follow_button=Button(),
        stop_follow_button=Button(),
        follow_status_label=Label(),
        _logger=logging.getLogger("async_page_start_test"),
    )
    Poe2CaptureTestPage._on_follow_lifecycle_finished(
        page, 1, "start", False, RuntimeError("spawn failed")
    )
    assert page._follow_engine_page_adapter is None
    assert page._follow_engine_composition is None
    assert page._follow_engine_adapter_owned is False


def test_modular_start_is_deferred_while_previous_stop_is_pending():
    """A restart must not reuse a composition whose queue is being disposed."""
    page = SimpleNamespace(
        _modular_follow_stop_pending=True,
        _modular_follow_restart_requested=False,
        _logger=logging.getLogger("page_start_test"),
    )
    assert Poe2CaptureTestPage._start_modular_follow_experiment(page) is True
    assert page._modular_follow_restart_requested is True


def test_follow_button_never_falls_back_to_legacy_runtime():
    """The formal follow entry must fail closed when modular wiring is absent."""
    messages = []
    legacy_calls = []
    page = SimpleNamespace(
        _follow_engine_page_adapter=None,
        _follow_engine_page_adapter_factory=None,
        _logger=logging.getLogger("page_start_test"),
        follow_status_label=SimpleNamespace(setText=messages.append),
        _make_follow_runtime=lambda *args, **kwargs: legacy_calls.append((args, kwargs)),
    )

    Poe2CaptureTestPage.start_follow_experiment(page)

    assert legacy_calls == []
    assert messages and "旧版跟随已禁用" in messages[-1]


def test_pending_restart_starts_only_after_stop_releases_owned_composition():
    class Button:
        def setEnabled(self, _value):
            pass

    class Label:
        def setText(self, _value):
            pass

    class Timer:
        def stop(self):
            pass

        def setInterval(self, _value):
            pass

    calls = []
    page = SimpleNamespace(
        _follow_lifecycle_serial=4,
        _modular_follow_stop_pending=True,
        _modular_follow_start_pending=False,
        _modular_follow_active=False,
        _modular_follow_live_mode=False,
        _modular_follow_restart_requested=True,
        _follow_timer=Timer(),
        _follow_timer_default_interval=100,
        _follow_engine_adapter_owned=True,
        _follow_engine_page_adapter=object(),
        _follow_engine_composition=object(),
        start_follow_button=Button(),
        stop_follow_button=Button(),
        follow_status_label=Label(),
        _dual_motion_tracker=None,
        _last_dual_first_frame_result=None,
        _logger=logging.getLogger("page_start_test"),
    )
    page._start_modular_follow_experiment = lambda: calls.append(True) or True
    Poe2CaptureTestPage._on_follow_lifecycle_finished(page, 4, "stop", True, None)
    assert calls == [True]
    assert page._follow_engine_page_adapter is None
    assert page._follow_engine_composition is None
