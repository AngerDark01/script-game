from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "auto_modules"


def _production_python_files(root: Path):
    return (
        path
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts
    )


def _violations(root: Path, pattern: str) -> list[str]:
    matcher = re.compile(pattern)
    found = []
    for path in _production_python_files(root):
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if matcher.search(line):
                found.append(f"{path.relative_to(ROOT)}:{line_number}: {line.strip()}")
    return found


def test_core_does_not_import_application_adapters_ui_or_features():
    found = _violations(
        SOURCE / "core",
        r"(?:from|import) auto_modules\.(?:application|adapters|ui|features)(?:\.|\s|$)",
    )
    assert not found, "\n".join(found)


def test_core_does_not_name_concrete_game_business_concepts():
    found = _violations(
        SOURCE / "core",
        r"\b(?:portal|loot|torchlight|poe2)\b",
    )
    assert not found, "\n".join(found)


def test_navigation_ui_uses_game_composition_instead_of_feature_definitions():
    found = _violations(
        SOURCE / "ui" / "modes" / "navigation",
        r"(?:from|import) auto_modules\.features\.torchlight\.(?:portal|loot)(?:\.|\s|$)",
    )
    assert not found, "\n".join(found)


def test_generic_navigation_and_event_ui_do_not_name_game_business_concepts():
    roots = [
        SOURCE / "ui" / "modes" / "navigation",
        SOURCE / "ui" / "dialogs" / "event_manager",
    ]
    found = []
    for root in roots:
        found.extend(_violations(root, r"(?i)\b(?:portal|loot|torchlight|poe2)\b"))
    assert not found, "\n".join(found)


def test_navigation_registry_defaults_to_generic_empty_composition():
    from auto_modules.ui.modes.navigation.event_adapter import create_default_event_registry

    assert create_default_event_registry().definitions() == []


def test_generic_event_ui_does_not_import_game_specific_ui():
    found = _violations(
        SOURCE / "ui" / "modes" / "events",
        r"(?:from|import).*torchlight",
    )
    assert not found, "\n".join(found)


def test_production_code_does_not_import_tools():
    found = _violations(SOURCE, r"(?:from|import) tools(?:\.|\s|$)")
    assert not found, "\n".join(found)


def test_hybrid_localization_experiment_has_no_ui_or_input_execution_dependencies():
    root = (
        SOURCE
        / "features"
        / "poe2"
        / "live_terrain"
        / "experimental"
        / "hybrid_localization"
    )
    found = _violations(
        root,
        r"(?:from|import) (?:PySide6|auto_modules\.(?:ui|application|adapters\.host|services\.lan|core\.gamepad))(?:\.|\s|$)",
    )
    assert not found, "\n".join(found)


def test_game_feature_packages_are_importable_without_runtime_side_effects():
    import auto_modules.features.poe2
    import auto_modules.features.poe2.live_terrain
    import auto_modules.features.torchlight
    import auto_modules.features.torchlight.portal
    import auto_modules.features.torchlight.loot
    import auto_modules.features.torchlight.follow
    import auto_modules.features.torchlight.skills
    import auto_modules.ui.modes.torchlight.follow

    assert auto_modules.features.torchlight.__all__ == ()


def test_poe2_live_terrain_business_has_one_feature_home():
    assert (SOURCE / "features" / "poe2" / "live_terrain").is_dir()
    assert not any((SOURCE / "adapters" / "poe2_live_terrain").glob("*.py"))
    assert not any((ROOT / "tools" / "experiments" / "poe2_live_terrain").glob("*.py"))

    found = _violations(
        SOURCE,
        r"auto_modules\.(?:adapters\.poe2_live_terrain|tools\.experiments\.poe2_live_terrain)",
    )
    assert not found, "\n".join(found)


def test_poe2_ui_composition_owns_feature_assembly(tmp_path):
    import numpy as np
    from auto_modules.core.vision import HSVRecognizer

    from auto_modules.features.poe2.live_terrain import (
        Poe2HybridProductRuntime,
        Poe2MonitorConfigStore,
        Poe2TerrainService,
    )
    from auto_modules.ui.modes.poe2 import build_poe2_live_terrain_composition

    class Capture:
        def capture(self, _x, _y, width, height):
            return np.zeros((height, width, 3), dtype=np.uint8)

    class Recognizer:
        def extract_player(self, frame):
            return np.zeros(frame.shape[:2], dtype=np.uint8)

        def extract_walls(self, frame):
            return np.zeros(frame.shape[:2], dtype=np.uint8)

    composition = build_poe2_live_terrain_composition(
        screen_capture=Capture(),
        recognizer=Recognizer(),
        writable_root=tmp_path,
    )
    assert isinstance(composition.service, Poe2TerrainService)
    assert isinstance(composition.runtime, Poe2HybridProductRuntime)
    assert isinstance(composition.config_store, Poe2MonitorConfigStore)
    assert composition.config_store.root == (tmp_path / "poe2_live_terrain").resolve()


def test_poe2_composition_copies_mutable_hsv_recognizer_state(tmp_path):
    import numpy as np

    from auto_modules.core.vision import HSVRecognizer
    from auto_modules.ui.modes.poe2 import build_poe2_live_terrain_composition

    class Capture:
        def capture(self, _x, _y, width, height):
            return np.zeros((height, width, 3), dtype=np.uint8)

    shared = HSVRecognizer()
    composition = build_poe2_live_terrain_composition(
        screen_capture=Capture(),
        recognizer=shared,
        writable_root=tmp_path,
    )

    dedicated = composition.capture_recognizer
    assert isinstance(dedicated, HSVRecognizer)
    assert dedicated is not shared
    shared.player_hsv_min[:] = 0
    assert dedicated.player_hsv_min.tolist() != [0, 0, 0]


def test_torchlight_composition_owns_torchlight_event_registration():
    from auto_modules.core.events.config import apply_registered_event_defaults
    from auto_modules.core.events.config_model import DEFAULT_EVENT_CONFIG, EventSystemConfig
    from auto_modules.features.torchlight.composition import build_torchlight_feature_registry

    registry = build_torchlight_feature_registry()
    assert {definition.event_type for definition in registry.definitions()} == {"portal", "loot"}
    assert DEFAULT_EVENT_CONFIG["events"] == {}

    config = apply_registered_event_defaults(registry, EventSystemConfig.default())
    assert config.event("portal")["detector_mode"] == "shape_color"
    assert config.event("loot")["detector_mode"] == "async_feature_match"

    portal_schema = registry.get("portal").config_schema()
    loot_schema = registry.get("loot").config_schema()
    assert portal_schema["detector_mode"]["compact"] is True
    assert portal_schema["interaction"]["summary"] is True
    assert loot_schema["player_center_mask_radius"]["compact"] is True
    assert loot_schema["pickup_radius"]["summary"] is True


def test_torchlight_navigation_composition_provides_business_ui_adapters():
    from auto_modules.core.events.config_model import EventSystemConfig
    from auto_modules.ui.modes.navigation.presentation import EventOverlayContext
    from auto_modules.ui.modes.torchlight.navigation import (
        build_loot_debug_overlays,
        build_torchlight_navigation_composition,
    )

    composition = build_torchlight_navigation_composition()
    assert composition.event_registry_factory().get("portal") is not None
    assert composition.event_registry_factory().get("loot") is not None
    assert composition.event_overlay_providers == (build_loot_debug_overlays,)

    config = EventSystemConfig.from_dict({
        "events": {
            "loot": {
                "enabled": True,
                "player_center_mask_enabled": True,
                "player_center_mask_overlay_enabled": True,
                "player_center_mask_radius": 28,
            }
        }
    })
    overlays = build_loot_debug_overlays(EventOverlayContext(
        event_config=config,
        player_global_pos=(100.0, 200.0),
        draw_scale=2.0,
    ))
    assert len(overlays) == 1
    assert overlays[0].global_pos == (100.0, 200.0)
    assert overlays[0].scene_radius == 56.0


def test_torchlight_event_assets_live_under_game_resource_domain():
    from auto_modules.features.torchlight.loot.assets import (
        LOOT_MINIMAP_TEMPLATE_DIR,
        LOOT_PLAYER_MARKER_EXCLUDE_DIR,
    )
    from auto_modules.features.torchlight.portal.assets import (
        PORTAL_MAIN_VIEW_PARAMS,
        PORTAL_MINIMAP_TEMPLATES,
    )

    expected_root = ROOT / "resources" / "games" / "torchlight"
    paths = [
        LOOT_MINIMAP_TEMPLATE_DIR,
        LOOT_PLAYER_MARKER_EXCLUDE_DIR,
        PORTAL_MAIN_VIEW_PARAMS,
        *PORTAL_MINIMAP_TEMPLATES,
    ]
    assert all(expected_root in path.parents for path in paths)
    assert all(path.exists() for path in paths)
