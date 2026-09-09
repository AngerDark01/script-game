"""Writable paths for installed builds; source runs retain their original layout."""
import os
from pathlib import Path


def data_root(project_root: Path) -> Path:
    configured = os.environ.get('AUTO_MODULES_DATA_DIR')
    return Path(configured).resolve() if configured else Path(project_root).resolve()
