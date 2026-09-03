from __future__ import annotations

import json
from pathlib import Path

from .models import BindingProfile


def load_profile(path: Path) -> BindingProfile:
    if not path.exists():
        return BindingProfile()
    return BindingProfile.from_payload(json.loads(path.read_text(encoding="utf-8")))


def save_profile(path: Path, profile: BindingProfile) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(profile.to_payload(), indent=2), encoding="utf-8")
    temporary.replace(path)
