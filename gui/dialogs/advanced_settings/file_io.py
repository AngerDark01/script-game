from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from ...composition.paths import advanced_settings_dir_from_file

DEFAULT_ADVANCED_SETTINGS_DIR = advanced_settings_dir_from_file(__file__)
_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')


def advanced_settings_output_dir(output_dir: str | Path | None = None) -> Path:
    """Return the explicit directory used for saved advanced-setting snapshots."""
    return Path(output_dir) if output_dir is not None else DEFAULT_ADVANCED_SETTINGS_DIR


def save_params_snapshot(
    param_name: str,
    parameters: Mapping[str, Any],
    output_dir: str | Path | None = None,
    now: datetime | None = None,
) -> Path:
    """Persist a named parameter snapshot and return the written JSON path."""
    cleaned_name = _safe_filename_part(param_name)
    if not cleaned_name:
        raise ValueError("Parameter name is required")

    snapshot_time = now or datetime.now()
    target_dir = advanced_settings_output_dir(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    target_path = target_dir / f"params_{cleaned_name}_{snapshot_time:%Y%m%d_%H%M%S}.json"
    payload = {
        "name": param_name,
        "timestamp": snapshot_time.isoformat(),
        "parameters": parameters,
    }

    with target_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)

    return target_path


def load_params_snapshot(path: str | Path) -> dict[str, Any]:
    """Load and validate a parameter snapshot JSON file."""
    source_path = Path(path)
    with source_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, dict):
        raise ValueError("Parameter file must contain a JSON object")
    if "parameters" not in payload:
        raise ValueError("Parameter file is missing the 'parameters' field")
    if not isinstance(payload["parameters"], dict):
        raise ValueError("Parameter file field 'parameters' must be an object")

    return payload


def format_params_for_display(parameters: Mapping[str, Any]) -> str:
    return json.dumps(parameters, indent=2, ensure_ascii=False)


def _safe_filename_part(value: str) -> str:
    return _INVALID_FILENAME_CHARS.sub("_", value.strip()).strip(" ._")
