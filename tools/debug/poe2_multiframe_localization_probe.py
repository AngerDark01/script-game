"""Replay a saved native multi-frame localization archive offline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.absolute_registrar import AnchoredAbsoluteRegistrar
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.archive import COORDINATE_SPACE, MultiframeArchive
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.coordinator import MultiframeLocalizationCoordinator
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.evidence_window import EvidenceWindow
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.rolling_submap import RollingSubmap
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.strategy_a import StitchThenRegister, SubmapThresholds
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.strategy_b import JointCandidateStrategy


def _candidate_payload(candidate) -> dict[str, object]:
    transform = candidate.transform
    return {
        "position": list(candidate.position),
        "error": float(candidate.error),
        "score": float(candidate.score),
        "holdout_error": float(candidate.holdout_error),
        "support_frames": list(candidate.support_frames),
        "refinement_level": candidate.refinement_level,
        "transform": {
            "angle_degrees": float(transform.angle_degrees),
            "reflect_horizontal": bool(transform.reflect_horizontal),
            "scale": float(transform.scale),
            "translation": list(transform.translation),
        },
    }


def _estimate_payload(estimate) -> dict[str, object]:
    return {
        "status": estimate.status,
        "position": None if estimate.position is None else list(estimate.position),
        "source": estimate.source,
        "reason": estimate.reason,
        "registration_version": estimate.registration_version,
        "evidence_version": estimate.evidence_version,
        "fresh": estimate.fresh,
        "diagnostics": dict(estimate.diagnostics),
    }


def replay_archive(path: Path, *, strategy: str = "both") -> dict[str, object]:
    if strategy not in {"a", "b", "both"}:
        raise ValueError("strategy must be a, b or both")
    bundle = MultiframeArchive().load(path)
    window = EvidenceWindow(
        max_keyframes=max(24, len(bundle.evidence) + 1),
        max_window_ms=24 * 60 * 60 * 1000,
        max_travel_distance=1_000_000.0,
        max_bytes=2 * 1024 * 1024 * 1024,
    )
    submap = RollingSubmap()
    strategy_a = StitchThenRegister(
        AnchoredAbsoluteRegistrar(),
        thresholds=SubmapThresholds(min_frames=3, min_wall_pixels=8, min_span=3.0),
    )
    strategy_b = JointCandidateStrategy(min_support_frames=3)
    coordinator = MultiframeLocalizationCoordinator(
        instance_id=bundle.instance_id,
        window=window,
        submap=submap,
        strategy_a=strategy_a,
        strategy_b=strategy_b,
        reference=bundle.reference,
    )
    coordinator.set_strategies_enabled(
        strategy_a=strategy in {"a", "both"},
        strategy_b=strategy in {"b", "both"},
    )
    coordinator.start()
    coordinator.accept_anchor(bundle.anchor)
    for evidence in bundle.evidence:
        coordinator.ingest(evidence, defer_registration=True)
    request = coordinator.prepare_registration_request()
    if request is None:
        estimate = coordinator.last_estimate or coordinator._estimate(
            "replay_has_no_registration_request",
            status="collecting",
        )
    else:
        estimate = coordinator.apply_registration_outcome(coordinator.evaluate_registration(request))
    result_a = coordinator.last_strategy_a_result
    result_b = coordinator.last_strategy_b_result
    candidates = tuple(getattr(result_b, "candidates", ()) or ())
    return {
        "coordinate_space": COORDINATE_SPACE,
        "instance_id": bundle.instance_id,
        "evidence_count": len(bundle.evidence),
        "strategy": strategy,
        "strategy_a": {
            "status": getattr(result_a, "status", "disabled" if strategy == "b" else "not_run"),
            "reason": getattr(result_a, "reason", ""),
        },
        "strategy_b": {
            "candidate_count": len(candidates),
            "candidates": [_candidate_payload(item) for item in candidates],
        },
        "final_estimate": _estimate_payload(estimate),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay", type=Path, required=True, help="native schema-3 archive directory")
    parser.add_argument("--strategy", choices=("a", "b", "both"), default="both")
    parser.add_argument("--json", action="store_true", help="reserved for scripting; output is always JSON")
    args = parser.parse_args()
    try:
        report = replay_archive(args.replay, strategy=args.strategy)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
