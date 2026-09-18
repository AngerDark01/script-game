from auto_modules.ui.virtual_gamepad.models import BindingProfile, CONTROLS, DualUiStatus, StateSnapshot


def test_state_snapshot_reads_host_camel_case_payload():
    state = StateSnapshot.from_payload({"buttons": 0x1000, "leftTrigger": 123, "rightStickY": -321})
    assert state.is_pressed("A")
    assert state.left_trigger == 123
    assert state.right_stick_y == -321


def test_profile_supports_multiple_sources_per_control():
    profile = BindingProfile.from_payload({"bindings": [{"source": "keyboard:W", "target": "LeftStick"}, {"source": "keyboard:Up", "target": "LeftStick"}]})
    assert profile.bindings["LeftStick"] == ["keyboard:W", "keyboard:Up"]


def test_dual_status_reads_both_controller_slots():
    status = DualUiStatus.from_payload({
        "controllers": [
            {"controller": 1, "runState": "running"},
            {"controller": 2, "runState": "paused"},
        ]
    })
    assert status.for_controller(1).run_state == "running"
    assert status.for_controller(2).run_state == "paused"


def test_profile_keeps_mouse_sensitivity_and_exposes_stick_click_controls():
    profile = BindingProfile.from_payload({"mouseSensitivity": 4.0})

    assert profile.mouse_sensitivity == 4.0
    assert profile.to_payload()["mouseSensitivity"] == 4.0
    assert "LeftStickClick" in CONTROLS
    assert "RightStickClick" in CONTROLS


def test_profile_enables_native_mouse_movement_passthrough_by_default():
    profile = BindingProfile.from_payload({})

    assert profile.mouse_move_passthrough is True
    assert profile.to_payload()["mouseMovePassthrough"] is True
