from __future__ import annotations

import json
from pathlib import Path

from .profiles import TargetProfile


def load_target_profile(path: str | Path) -> TargetProfile:
    profile_path = Path(path)
    payload = json.loads(profile_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("perception profile must be a JSON object")
    return TargetProfile.from_dict(payload)


def save_target_profile(path: str | Path, profile: TargetProfile) -> None:
    profile_path = Path(path)
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = profile_path.with_suffix(profile_path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(profile.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary_path.replace(profile_path)
