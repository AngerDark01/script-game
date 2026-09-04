from pathlib import Path

from virtual_gamepad_ui.models import BindingProfile
from virtual_gamepad_ui.profile_store import load_profile, load_profiles, save_profile


def test_profile_round_trip(tmp_path: Path):
    path = tmp_path / "profile.json"
    profile = BindingProfile(bindings={"A": ["keyboard:Space"]}, start_pause="F7")

    save_profile(path, profile)

    loaded = load_profile(path)
    assert loaded.to_payload() == profile.to_payload()


def test_controller_profiles_are_independent(tmp_path: Path):
    first_path = tmp_path / "controller-1.json"
    second_path = tmp_path / "controller-2.json"
    save_profile(first_path, BindingProfile(bindings={"A": ["keyboard:J"]}, start_pause="F7"))
    save_profile(second_path, BindingProfile(bindings={"B": ["keyboard:K"]}, start_pause="F8"))

    profiles = load_profiles(first_path, second_path)

    assert profiles[1].bindings == {"A": ["keyboard:J"]}
    assert profiles[2].bindings == {"B": ["keyboard:K"]}
    assert profiles[1].start_pause == "F7"
    assert profiles[2].start_pause == "F8"
