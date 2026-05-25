from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
PORTAL_MINIMAP_TEMPLATES = [
    ROOT / "assets" / "event_templates" / "portal" / "minimap" / "portal_minimap_01.png",
    ROOT / "assets" / "event_templates" / "portal" / "minimap" / "portal_minimap_02.png",
]
PORTAL_MAIN_VIEW_PARAMS = ROOT / "assets" / "event_detectors" / "portal" / "main_view" / "blue_glow_detector_v1.json"
