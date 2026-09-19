import pytest

from auto_modules.core.localization.observations import (
    ObservationCandidate,
    ObservationFrame,
)


def test_candidate_requires_finite_local_position_and_confidence():
    with pytest.raises(ValueError):
        ObservationCandidate(local_position=(1, 2), confidence=1.2)


def test_observation_keeps_all_candidates_and_selected_identity():
    first = ObservationCandidate(
        local_position=(12, 18),
        confidence=0.91,
        identity_hint="primary",
    )
    second = ObservationCandidate(local_position=(80, 42), confidence=0.77)
    frame = ObservationFrame(
        captured_at_ms=100,
        candidates=(first, second),
        selected_index=0,
        source="synthetic",
    )
    assert frame.selected.local_position == (12, 18)
    assert len(frame.candidates) == 2
    assert frame.is_fresh is True
