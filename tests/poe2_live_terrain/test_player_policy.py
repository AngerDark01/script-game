from auto_modules.core.localization.observations import ObservationCandidate, ObservationFrame
from auto_modules.features.poe2.live_terrain.player_policy import (
    select_single_player,
    select_single_player_frame,
)


def test_single_player_policy_selects_only_high_confidence_candidate():
    frame = ObservationFrame(
        captured_at_ms=10,
        candidates=(ObservationCandidate((12, 14), 0.88), ObservationCandidate((80, 80), 0.35)),
    )
    selected = select_single_player(frame, min_confidence=0.7)
    assert selected.local_position == (12, 14)
    assert select_single_player_frame(frame).selected_index == 0


def test_single_player_policy_returns_none_without_a_valid_candidate():
    frame = ObservationFrame(captured_at_ms=10, candidates=())
    assert select_single_player(frame, min_confidence=0.7) is None


def test_single_player_policy_fails_closed_on_ambiguity():
    frame = ObservationFrame(
        captured_at_ms=10,
        candidates=(ObservationCandidate((12, 14), 0.88), ObservationCandidate((80, 80), 0.9)),
    )
    assert select_single_player(frame) is None
