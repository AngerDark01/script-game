from dataclasses import replace

from auto_modules.features.poe2.live_terrain.experimental.application.models import (
    ExperimentSessionState,
    ExperimentPhase,
)
from auto_modules.features.poe2.live_terrain.experimental.follow.models import (
    FollowSessionState,
    VisualRoleObservation,
)
from auto_modules.features.poe2.live_terrain.experimental.recovery.models import (
    RecoveryEpisodeState,
)


def test_session_state_transition_is_explicit_and_does_not_mutate_input():
    state = ExperimentSessionState(session_id="s1")
    running = state.transition(ExperimentPhase.RUNNING)

    assert state.phase is ExperimentPhase.IDLE
    assert running.phase is ExperimentPhase.RUNNING
    assert running.session_id == "s1"


def test_follow_state_has_bounded_visual_observation_by_role():
    observation = VisualRoleObservation(
        role_key="local-device:p2",
        position=(12.0, 4.0),
        captured_at_ms=100,
        visible=False,
        source="command_prediction",
        uncertainty_native=2.5,
    )
    state = FollowSessionState(session_id="s1").with_observation(observation)

    assert state.observations["local-device:p2"] == observation
    assert state.observations is not state.observations.copy()


def test_recovery_episode_backoff_is_bounded_and_resettable():
    episode = RecoveryEpisodeState(session_id="s1")
    scheduled = episode.schedule_retry("visual_stall")

    assert scheduled.retry_delay_ms == 5_000
    assert scheduled.next_retry_delay_ms == 10_000
    assert scheduled.schedule_count == 1
    assert scheduled.clear().schedule_count == 0
