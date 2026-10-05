from __future__ import annotations

import math

import pytest

from auto_modules.features.poe2.live_terrain import (
    POE2_MAP_TO_STICK_BASIS,
    native_map_vector_to_local,
    native_route_vector_for_program_output,
)
from auto_modules.core.localization.displacement import transform_local_displacement


def _apply(vector: tuple[float, float]) -> tuple[float, float]:
    a, b, c, d = POE2_MAP_TO_STICK_BASIS
    return (a * vector[0] + b * vector[1], c * vector[0] + d * vector[1])


def test_poe2_basis_maps_native_axes_to_isometric_stick_axes() -> None:
    native_x = _apply((1.0, 0.0))
    native_y = _apply((0.0, 1.0))

    assert native_x == (0.5, 0.5)
    assert native_y == (-0.5, 0.5)
    assert math.isclose(native_x[0] * native_y[0] + native_x[1] * native_y[1], 0.0)


def test_route_vector_is_inverse_rotated_before_game_input():
    # The registered map says local right is native up at +90 degrees.  A
    # native up route must therefore be sent as local right, not native up.
    assert native_map_vector_to_local(
        (0.0, -4.0), angle_degrees=90.0, reflect_horizontal=False, scale=2.0
    ) == pytest.approx((2.0, 0.0), abs=1e-6)


def test_route_vector_applies_reflection_in_inverse_order():
    local = (3.0, -1.0)
    native = transform_local_displacement(
        local, angle_degrees=37.0, reflect_horizontal=True, scale=1.0,
    )
    assert native_map_vector_to_local(
        native, angle_degrees=37.0, reflect_horizontal=True, scale=1.0,
    ) == pytest.approx(local, abs=1e-6)


def test_program_route_vector_stays_in_registered_native_frame() -> None:
    native = (0.2039557812, -0.9789801016)

    assert native_route_vector_for_program_output(native) == native


def test_registration_is_not_applied_a_second_time_at_input_boundary() -> None:
    native = (0.2039557812, -0.9789801016)
    direct_stick = _apply(native)
    wrongly_inverse_registered = _apply(
        native_map_vector_to_local(
            native,
            angle_degrees=221.0,
            reflect_horizontal=True,
            scale=0.863,
        )
    )

    assert direct_stick != pytest.approx(wrongly_inverse_registered, abs=1e-3)
    assert _apply(native_route_vector_for_program_output(native)) == pytest.approx(
        direct_stick, abs=1e-9
    )
