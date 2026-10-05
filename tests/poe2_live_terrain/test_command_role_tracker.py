import numpy as np
import pytest

from auto_modules.features.poe2.live_terrain.experimental.multiplayer_follow.command_role_tracker import (
    CommandRoleTracker,
)


def test_successful_output_is_replayed_only_until_ttl_and_new_output_replaces_old():
    tracker = CommandRoleTracker(expected_speed=20.0)
    tracker.seed("p2", "map-1", (10.0, 10.0), captured_at_ms=1000)
    tracker.record_output("p2", (1.0, 0.0), accepted_at_ms=1000, ttl_ms=100)
    tracker.record_output("p2", (0.0, 1.0), accepted_at_ms=1050, ttl_ms=100)

    at_1200 = tracker.estimate("p2", now_ms=1200)
    assert at_1200.position == pytest.approx((11.0, 12.0))
    assert at_1200.source == "command_prediction"
    assert at_1200.last_visual_at_ms == 1000
    assert tracker.estimate("p2", now_ms=1500).position == pytest.approx(at_1200.position)


def test_delayed_visual_correction_replays_later_commands_without_double_counting():
    tracker = CommandRoleTracker(expected_speed=20.0)
    tracker.seed("p2", "map-1", (10.0, 10.0), captured_at_ms=1000)
    tracker.record_output("p2", (1.0, 0.0), accepted_at_ms=1000, ttl_ms=100)
    tracker.record_output("p2", (1.0, 0.0), accepted_at_ms=1100, ttl_ms=100)

    correction = tracker.observe(
        "p2", "map-1", (12.5, 10.0), captured_at_ms=1100,
        covariance=np.eye(2) * 0.01,
    )
    assert correction.accepted_observation
    estimate = tracker.estimate("p2", now_ms=1200)
    assert estimate.position[0] == pytest.approx(14.5, abs=0.15)
    assert estimate.last_visual_at_ms == 1100
    assert estimate.uncertainty_native < tracker.estimate("p2", now_ms=2000).uncertainty_native


def test_role_and_map_isolation_and_bad_observation_gate():
    tracker = CommandRoleTracker(expected_speed=20.0)
    tracker.seed("p1", "map-1", (5.0, 5.0), captured_at_ms=1000)
    tracker.seed("p2", "map-1", (10.0, 10.0), captured_at_ms=1000)
    tracker.record_output("p2", (1.0, 0.0), accepted_at_ms=1000, ttl_ms=100)
    rejected = tracker.observe(
        "p2", "map-1", (500.0, 500.0), captured_at_ms=1050,
        covariance=np.eye(2) * 0.01,
    )
    assert not rejected.accepted_observation
    assert tracker.estimate("p1", now_ms=1100).position == (5.0, 5.0)
    assert tracker.estimate("p2", now_ms=1100).position == pytest.approx((12.0, 10.0))
    with pytest.raises(ValueError, match="map"):
        tracker.observe("p2", "map-2", (10.0, 10.0), captured_at_ms=1100)


def test_visual_observation_does_not_accept_an_older_frame():
    tracker = CommandRoleTracker(expected_speed=20.0)
    tracker.seed("p2", "map-1", (10.0, 10.0), captured_at_ms=1000)
    tracker.observe("p2", "map-1", (11.0, 10.0), captured_at_ms=1100)
    with pytest.raises(ValueError, match="older"):
        tracker.observe("p2", "map-1", (9.0, 10.0), captured_at_ms=1050)


def test_default_visual_gate_tolerates_output_latency_but_rejects_explicit_jump():
    tracker = CommandRoleTracker(expected_speed=80.0)
    tracker.seed("p2", "map-1", (523.5, 1082.5), captured_at_ms=1000)
    tracker.record_output(
        "p2", (-0.1, 0.64), accepted_at_ms=1000, ttl_ms=160,
    )
    # The first fresh screenshot may still show the pre-command position while
    # the accepted Host pulse is taking effect.  This must correct the model,
    # not trigger the page's two-rejection re-anchor loop.
    latency_frame = tracker.observe(
        "p2", "map-1", (523.5, 1082.5), captured_at_ms=1231,
    )
    assert latency_frame.accepted_observation
    impossible = tracker.observe(
        "p2", "map-1", (900.0, 900.0), captured_at_ms=1264,
        covariance=np.eye(2) * 0.01,
    )
    assert not impossible.accepted_observation


def test_visual_phase_is_bounded_and_does_not_weaken_steady_state_jump_gate():
    tracker = CommandRoleTracker(expected_speed=80.0, visual_phase_grace_ms=200)
    tracker.seed("p2", "map-1", (0.0, 0.0), captured_at_ms=1000)
    tracker.arm_visual_phase("p2", started_at_ms=1000)

    # The first frame can still be at the anchor while output has already
    # been acknowledged; the bounded phase accepts that normal latency.
    during_phase = tracker.observe(
        "p2", "map-1", (12.0, 0.0), captured_at_ms=1100,
    )
    assert during_phase.accepted_observation
    assert tracker.visual_phase_active("p2", now_ms=1199)

    # Once the episode expires, the normal innovation gate is restored.
    assert not tracker.visual_phase_active("p2", now_ms=1200)
    rejected = tracker.observe(
        "p2", "map-1", (900.0, 900.0), captured_at_ms=1250,
        covariance=np.eye(2) * 0.01,
    )
    assert not rejected.accepted_observation


def test_rebase_visual_learns_speed_and_discards_stale_command_intervals():
    tracker = CommandRoleTracker(expected_speed=80.0)
    tracker.seed("p2", "map-1", (10.0, 10.0), captured_at_ms=1000)
    tracker.record_output("p2", (1.0, 0.0), accepted_at_ms=1000, ttl_ms=220)

    corrected = tracker.rebase_visual(
        "p2", "map-1", (12.0, 10.0), captured_at_ms=1200,
    )

    assert corrected.accepted_observation
    assert corrected.reason == "visual_continuity_rebase"
    diagnostics = tracker.diagnostics("p2", now_ms=1200)
    assert diagnostics["estimated_speed"] == pytest.approx(10.0)
    assert diagnostics["speed_samples"] == 1
    assert diagnostics["intervals"] == ()

    tracker.record_output("p2", (1.0, 0.0), accepted_at_ms=1200, ttl_ms=100)
    assert tracker.estimate("p2", now_ms=1300).position[0] == pytest.approx(13.0)


def test_visual_speed_is_not_multiplied_by_calibrator_gain_after_learning():
    tracker = CommandRoleTracker(expected_speed=80.0)
    tracker.seed("p2", "map-1", (10.0, 10.0), captured_at_ms=1000)
    tracker.rebase_visual("p2", "map-1", (12.0, 10.0), captured_at_ms=1200)

    # The visual EWMA is already 10 native units/s.  A calibrator gain is a
    # control-output correction and must not be applied a second time to this
    # measured position model.
    tracker.record_output(
        "p2", (1.0, 0.0), accepted_at_ms=1200, ttl_ms=100, speed_gain=0.5,
    )
    assert tracker.estimate("p2", now_ms=1300).position[0] == pytest.approx(13.0)
