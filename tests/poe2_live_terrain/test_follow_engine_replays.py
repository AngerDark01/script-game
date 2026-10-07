from __future__ import annotations

import json
from pathlib import Path

from auto_modules.features.poe2.live_terrain.experimental.follow_engine.replay import (
    ReplayEvent,
    ReplayManifest,
)


FIXTURE = Path(__file__).parent / "fixtures" / "follow_replays" / "scenarios.json"


def _load_scenarios() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _manifest_for(item: dict) -> ReplayManifest:
    return ReplayManifest(
        name=item["name"],
        map_instance="offline-map-v1",
        roles=("p1", "p2"),
        events=tuple(
            ReplayEvent(
                captured_at_ms=event["captured_at_ms"],
                kind=event["kind"],
                roles=event["roles"],
                expected_state=event["expected"]["state"],
                keep_session=event["expected"]["keep_session"],
            )
            for event in item["events"]
        ),
        real_input_allowed=False,
    )


def test_offline_fixture_contains_all_recovery_scenarios_and_no_input_permission():
    payload = _load_scenarios()
    names = {item["name"] for item in payload["scenarios"]}
    assert names == {
        "normal_dual",
        "single_frame_mismatch",
        "p2_short_occlusion",
        "p2_long_occlusion",
        "local_recovery_success",
        "memory_reanchor_success",
        "host_session_expired",
        "map_instance_changed",
    }
    assert payload["real_input_allowed"] is False


def test_offline_replay_manifests_are_ordered_and_deterministic():
    manifests = [_manifest_for(item) for item in _load_scenarios()["scenarios"]]
    assert all(manifest.events for manifest in manifests)
    assert all(manifest.real_input_allowed is False for manifest in manifests)
    assert all(manifest.signature() == manifest.signature() for manifest in manifests)
    assert all(
        [event.captured_at_ms for event in manifest.events]
        == sorted(event.captured_at_ms for event in manifest.events)
        for manifest in manifests
    )
