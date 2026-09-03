from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
LOOT_MINIMAP_TEMPLATE_DIR = ROOT / "assets" / "event_templates" / "loot" / "minimap"
LOOT_DISABLED_MINIMAP_TEMPLATE_STEMS = {
    # The gray diamond icon is low-value loot and is visually too close to
    # minimap pillars/blue event icons, so it is disabled for localization.
    "fef5a19f6713c9f973263eb8fbcff1a4",
}
LOOT_MINIMAP_TEMPLATES = [
    path
    for path in sorted(LOOT_MINIMAP_TEMPLATE_DIR.glob("*.png"))
    if path.stem not in LOOT_DISABLED_MINIMAP_TEMPLATE_STEMS
]
LOOT_PLAYER_MARKER_EXCLUDE_DIR = ROOT / "assets" / "event_templates" / "loot" / "exclude" / "player_marker"
LOOT_PLAYER_MARKER_EXCLUDE_TEMPLATES = sorted(LOOT_PLAYER_MARKER_EXCLUDE_DIR.glob("*.png"))
