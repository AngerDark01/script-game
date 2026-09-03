from virtual_gamepad_ui.models import BindingProfile, StateSnapshot


def test_state_snapshot_reads_host_camel_case_payload():
    state = StateSnapshot.from_payload({"buttons": 0x1000, "leftTrigger": 123, "rightStickY": -321})
    assert state.is_pressed("A")
    assert state.left_trigger == 123
    assert state.right_stick_y == -321


def test_profile_supports_multiple_sources_per_control():
    profile = BindingProfile.from_payload({"bindings": [{"source": "keyboard:W", "target": "LeftStick"}, {"source": "keyboard:Up", "target": "LeftStick"}]})
    assert profile.bindings["LeftStick"] == ["keyboard:W", "keyboard:Up"]
