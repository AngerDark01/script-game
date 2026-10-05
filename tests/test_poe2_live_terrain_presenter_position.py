from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from types import SimpleNamespace
from PySide6.QtWidgets import QApplication

from auto_modules.features.poe2.live_terrain.contracts import CaptureMetadata, TerrainSnapshot
from auto_modules.features.poe2.live_terrain.player_position import PlayerPositionSample
from auto_modules.ui.modes.poe2_live_terrain.presenter import (
    build_localization_presentation,
    frame_pixmap,
    localization_display_point,
    localization_source_point,
    present_snapshot,
)
from auto_modules.ui.modes.poe2_live_terrain.presenter import present_localization_overlay
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import (
    SimilarityTransform2D,
)


def _snapshot() -> TerrainSnapshot:
    metadata = CaptureMetadata("A", "h", "A:h", 20, 20, "2026-09-22T00:00:00+00:00")
    return TerrainSnapshot(
        metadata,
        np.zeros((20, 20), dtype=np.uint8),
        np.ones((20, 20), dtype=np.int8),
        np.full((20, 20), 255, dtype=np.uint8),
        np.zeros((20, 20), dtype=np.uint8),
        np.full((20, 20), 255, dtype=np.uint8),
    )


def test_presenter_draws_player_marker_at_grid_position():
    QApplication.instance() or QApplication([])
    sample = PlayerPositionSample.from_world(
        world=(250.0 / 23.0 * 9.0, 250.0 / 23.0 * 9.0, 0.0),
        captured_at="2026-09-22T03:27:56+00:00",
        area_instance="A:h",
    )

    plain = present_snapshot(_snapshot()).pixmap.toImage()
    marked = present_snapshot(_snapshot(), player_position=sample).pixmap.toImage()

    assert marked.pixelColor(9, 9) != plain.pixelColor(9, 9)


def test_localization_overlay_applies_registered_arbitrary_direction():
    QApplication.instance() or QApplication([])
    base = present_snapshot(_snapshot()).pixmap
    state = SimpleNamespace(
        trajectory=((10.0, 10.0),),
        position=(10.0, 10.0),
        registration=SimpleNamespace(
            transform=SimilarityTransform2D(
                angle_degrees=45.0,
                reflect_horizontal=True,
                scale=1.0,
                translation=(0.0, 0.0),
            )
        ),
    )

    rotated = present_localization_overlay(base, state)

    assert rotated.size() != base.size()


def test_frame_pixmap_detaches_non_contiguous_numpy_views():
    QApplication.instance() or QApplication([])
    source = np.zeros((24, 32, 3), dtype=np.uint8)
    flipped = np.fliplr(source)

    pixmap = frame_pixmap(flipped)

    assert not pixmap.isNull()
    assert (pixmap.width(), pixmap.height()) == (32, 24)


def test_frame_pixmap_rejects_unsupported_channel_count():
    QApplication.instance() or QApplication([])
    pixmap = frame_pixmap(np.zeros((24, 32, 1), dtype=np.uint8))

    assert pixmap.isNull()


def test_localization_display_point_matches_overlay_rotation_and_flip():
    transform = SimilarityTransform2D(
        angle_degrees=45.0,
        reflect_horizontal=True,
        scale=1.0,
        translation=(0.0, 0.0),
    )

    point = localization_display_point(
        (10.0, 10.0),
        source_size=(20, 20),
        transform=transform,
    )

    assert point[0] > 0.0
    assert point[1] > 0.0
    assert point != (10.0, 10.0)


def test_localization_source_point_is_inverse_for_rotated_reflected_map():
    transform = SimilarityTransform2D(
        angle_degrees=37.0,
        reflect_horizontal=True,
        scale=1.0,
        translation=(0.0, 0.0),
    )
    source = (6.25, 13.5)
    display = localization_display_point(source, source_size=(20, 20), transform=transform)
    restored = localization_source_point(display, source_size=(20, 20), transform=transform)

    assert np.allclose(restored, source, atol=1e-6)


def test_presentation_uses_registration_only_when_versions_match():
    registration = SimpleNamespace(
        transform=SimilarityTransform2D(31.0, False, 1.0, (0.0, 0.0))
    )
    estimate = SimpleNamespace(position=(8.0, 9.0), registration_version=2)

    stale = build_localization_presentation(
        estimate,
        registration=registration,
        coordinator_registration_version=3,
        trajectory=((7.0, 9.0), (8.0, 9.0)),
        candidates=(),
    )
    current = build_localization_presentation(
        estimate,
        registration=registration,
        coordinator_registration_version=2,
        trajectory=((7.0, 9.0), (8.0, 9.0)),
        candidates=(),
    )

    assert stale.registration is None
    assert stale.orientation_status == "waiting_for_automatic_calibration"
    assert current.registration is registration
    assert current.orientation_status == "automatic_calibration_confirmed"
