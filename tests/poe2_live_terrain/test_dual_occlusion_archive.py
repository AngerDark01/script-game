import json

import numpy as np

from auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization.models import (
    MarkerColorProfile,
    PlayerMarkerCandidate,
)
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization.occlusion_archive import (
    save_dual_occlusion_evidence,
)


def test_occlusion_archive_keeps_raw_profile_masks_and_candidate_costs(tmp_path):
    raw = np.zeros((20, 20, 3), dtype=np.uint8)
    raw[3:6, 4:7] = (255, 0, 0)
    profile = MarkerColorProfile("blue", hue_min=100, hue_max=130)
    candidate = PlayerMarkerCandidate(
        "blue-1", (5, 4), area=9, bbox=(4, 3, 3, 3),
        color_features={"identity_hint": "blue", "profile_index": 0},
    )

    folder = save_dual_occlusion_evidence(
        tmp_path, raw=raw, profiles=(profile,), candidates=(candidate,),
        frame_id=123, captured_at_ms=456,
        status="degraded", reason="markers_missing",
        diagnostics={"assignment": {"candidate_costs": [2.5]}},
    )

    assert (folder / "raw.png").exists()
    assert (folder / "mask_0.png").exists()
    manifest = json.loads((folder / "evidence.json").read_text(encoding="utf-8"))
    assert manifest["candidates"][0]["bbox"] == [4, 3, 3, 3]
    assert manifest["diagnostics"]["assignment"]["candidate_costs"] == [2.5]
