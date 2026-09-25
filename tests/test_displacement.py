import pytest
import numpy as np

from auto_modules.core.localization.displacement import transform_local_displacement
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.similarity_search import (
    transform_feature,
)


def test_identity_transform_preserves_shift():
    assert transform_local_displacement(
        (3.0, -2.0),
        angle_degrees=0.0,
        reflect_horizontal=False,
        scale=1.0,
    ) == pytest.approx((3.0, -2.0))


def test_rotation_and_scale_are_applied():
    assert transform_local_displacement(
        (2.0, 0.0),
        angle_degrees=90.0,
        reflect_horizontal=False,
        scale=2.0,
    ) == pytest.approx((0.0, -4.0), abs=1e-6)


def test_rotation_uses_same_image_axis_as_feature_matching():
    """A positive match angle rotates a local rightward vector upward in image space."""
    assert transform_local_displacement(
        (1.0, 0.0),
        angle_degrees=90.0,
        reflect_horizontal=False,
        scale=1.0,
    ) == pytest.approx((0.0, -1.0), abs=1e-6)


def test_displacement_matches_feature_point_transform_for_rotation_and_reflection():
    feature = np.zeros((40, 50), dtype=np.uint8)
    origin = (18.0, 21.0)
    delta = (3.5, -2.0)
    angle = 37.0
    scale = 1.25
    transformed_origin = transform_feature(
        feature,
        origin,
        angle=angle,
        reflect_horizontal=True,
        scale=scale,
    ).player_position
    transformed_target = transform_feature(
        feature,
        (origin[0] + delta[0], origin[1] + delta[1]),
        angle=angle,
        reflect_horizontal=True,
        scale=scale,
    ).player_position
    actual = transform_local_displacement(
        delta,
        angle_degrees=angle,
        reflect_horizontal=True,
        scale=scale,
    )
    assert (
        transformed_target[0] - transformed_origin[0],
        transformed_target[1] - transformed_origin[1],
    ) == pytest.approx(actual, abs=1e-5)


def test_reflection_is_applied_before_rotation():
    assert transform_local_displacement(
        (2.0, 0.0),
        angle_degrees=0.0,
        reflect_horizontal=True,
        scale=1.0,
    ) == pytest.approx((-2.0, 0.0))


@pytest.mark.parametrize("shift", [(float("nan"), 0.0), (0.0, float("inf"))])
def test_non_finite_shift_is_rejected(shift):
    with pytest.raises(ValueError, match="finite"):
        transform_local_displacement(
            shift,
            angle_degrees=0.0,
            reflect_horizontal=False,
            scale=1.0,
        )
