from __future__ import annotations

from auto_modules.paths import resource_root


ROOT = resource_root()
TORCHLIGHT_ROOT = ROOT / "games" / "torchlight"
PORTAL_MINIMAP_TEMPLATES = [
    TORCHLIGHT_ROOT / "event_templates" / "portal" / "minimap" / "portal_minimap_01.png",
    TORCHLIGHT_ROOT / "event_templates" / "portal" / "minimap" / "portal_minimap_02.png",
]
PORTAL_MAIN_VIEW_PARAMS = TORCHLIGHT_ROOT / "event_detectors" / "portal" / "main_view" / "blue_glow_detector_v1.json"
