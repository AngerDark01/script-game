from auto_modules.core.localization.bounded_observation import BoundedRoleObservations


def test_missing_role_has_bounded_position_without_refreshing_last_seen():
    roles = BoundedRoleObservations(max_age_ms=2000, max_uncertainty=10)
    roles.seed("left", (10, 20), at_ms=100)
    roles.seed("right", (30, 40), at_ms=100)

    hidden = roles.update("left", at_ms=1100, candidate=None)
    visible = roles.update("right", at_ms=1100, candidate=(31, 40))

    assert hidden.available and not hidden.visible
    assert hidden.position == (10, 20)
    assert hidden.last_seen_at_ms == 100
    assert hidden.uncertainty > visible.uncertainty
    assert visible.visible and visible.position == (31, 40)
    assert not roles.update("left", at_ms=2201, candidate=None).available


def test_reappearance_requires_two_nearby_frames_after_occlusion():
    roles = BoundedRoleObservations(reappearance_frames=2, reappearance_after_missing=2)
    roles.seed("actor", (10, 10), at_ms=100)
    roles.update("actor", at_ms=200, candidate=None)
    roles.update("actor", at_ms=300, candidate=None)

    first = roles.update("actor", at_ms=400, candidate=(12, 10))
    assert not first.visible and first.position == (10, 10)
    assert not roles.update("actor", at_ms=500, candidate=(35, 35)).visible
    assert not roles.update("actor", at_ms=600, candidate=(12, 10)).visible
    second = roles.update("actor", at_ms=700, candidate=(12.5, 10))
    assert second.visible and second.position == (12.5, 10)


def test_continuous_observation_keeps_upstream_motion_gate():
    roles = BoundedRoleObservations()
    roles.seed("actor", (10, 10), at_ms=100)
    seen = roles.update("actor", at_ms=133, candidate=(20, 10))
    assert seen.visible and seen.position == (20, 10)


def test_expired_role_requires_two_frames_near_fresh_reacquisition_reference():
    roles = BoundedRoleObservations(max_age_ms=70, reappearance_frames=2)
    roles.seed("actor", (10, 10), at_ms=100)
    assert not roles.update("actor", at_ms=200, candidate=None).available
    assert not roles.update(
        "actor", at_ms=233, candidate=(40, 10),
        reacquisition_reference=(40, 10), reacquisition_radius=5,
    ).visible
    seen = roles.update(
        "actor", at_ms=266, candidate=(41, 10),
        reacquisition_reference=(41, 10), reacquisition_radius=5,
    )
    assert seen.visible and seen.position == (41, 10)
