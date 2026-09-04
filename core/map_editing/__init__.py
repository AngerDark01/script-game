"""Device-independent map wall correction models, composition, and storage."""

from .composition import compose_effective_wall_layer
from .models import WallOverrideDocument
from .operations import WallMaskPatch, apply_circular_brush
from .snapshot_operations import WallLayerPatch, apply_wall_brush
from .storage import load_wall_overrides, save_wall_overrides
from .version_storage import (
    WallVersion,
    WallVersionCatalog,
    activate_wall_version,
    load_wall_version_catalog,
    migrate_legacy_wall_overrides,
    save_new_wall_version,
)

__all__ = [
    "WallMaskPatch",
    "WallLayerPatch",
    "WallVersion",
    "WallVersionCatalog",
    "activate_wall_version",
    "WallOverrideDocument",
    "apply_circular_brush",
    "apply_wall_brush",
    "compose_effective_wall_layer",
    "load_wall_overrides",
    "load_wall_version_catalog",
    "migrate_legacy_wall_overrides",
    "save_new_wall_version",
    "save_wall_overrides",
]
