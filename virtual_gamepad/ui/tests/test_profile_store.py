from pathlib import Path

from virtual_gamepad_ui.models import BindingProfile
from virtual_gamepad_ui.profile_store import load_profile, save_profile


def test_profile_round_trip(tmp_path: Path):
    path = tmp_path / "profile.json"
    profile = BindingProfile(bindings={"A": ["keyboard:Space"]}, start_pause="F8")

    save_profile(path, profile)

    loaded = load_profile(path)
    assert loaded.to_payload() == profile.to_payload()
