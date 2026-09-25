from __future__ import annotations

import numpy as np

from auto_modules.core.localization import LocalizationResult
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import (
    AbsoluteRegistration,
    HybridFrame,
    SimilarityTransform2D,
)
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.local_corrector import LocalShapeCorrector
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.shape_registration import transform_points


def test_local_corrector_recovers_small_drift_without_global_search():
    wall = np.zeros((20, 20), dtype=np.uint8)
    wall[3:17, 4] = 255
    wall[15, 4:14] = 255
    player = (10.0, 10.0)
    true_position = (50.0, 50.0)
    truth = SimilarityTransform2D(0.0, False, 1.0, (40.0, 40.0))
    points = np.column_stack(np.nonzero(wall))[:, ::-1]
    projected = np.rint(transform_points(points, truth)).astype(int)
    reference = np.zeros((100, 100), dtype=np.uint8)
    reference[projected[:, 1], projected[:, 0]] = 255
    registration = AbsoluteRegistration(
        LocalizationResult((54.0, 50.0), 0.8, source="prediction", registration_valid=True),
        SimilarityTransform2D(0.0, False, 1.0, (44.0, 40.0)),
        0.0,
        "Map:A",
    )

    result = LocalShapeCorrector(
        translation_radius=5.0,
        translation_step=1.0,
        angle_radius=0.0,
        scale_radius=0.0,
        min_margin=0.0,
    ).correct(
        frame=HybridFrame(1, 100, wall, player),
        observed_mask=np.full_like(wall, 255),
        predicted_position=(54.0, 50.0),
        registration=registration,
        reference=reference,
    )

    assert result.accepted
    assert np.allclose(result.position, true_position, atol=1.0)
    assert result.search_bounds.width == 11
    assert result.search_bounds.height == 11
    assert result.diagnostics["tested_candidates"] <= 121


def test_local_corrector_rejects_empty_visual_evidence():
    registration = AbsoluteRegistration(
        LocalizationResult((10.0, 10.0), 0.8, source="prediction", registration_valid=True),
        SimilarityTransform2D(0.0, False, 1.0, (5.0, 5.0)),
        0.0,
        "Map:A",
    )
    empty = np.zeros((10, 10), dtype=np.uint8)

    result = LocalShapeCorrector().correct(
        frame=HybridFrame(1, 100, empty, (5.0, 5.0)),
        observed_mask=np.full_like(empty, 255),
        predicted_position=(10.0, 10.0),
        registration=registration,
        reference=np.zeros((30, 30), dtype=np.uint8),
    )

    assert not result.accepted
    assert result.reason == "insufficient_visual_structure"
