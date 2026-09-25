"""Explicit atomic JSON/NPZ archive for offline multi-frame diagnostics."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
import shutil
import tempfile
from types import MappingProxyType
from typing import Any, Mapping

import numpy as np

from auto_modules.core.localization.frame_displacement import FrameDisplacement
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import (
    HybridFrame,
    PositionAnchor,
    SimilarityTransform2D,
)
from auto_modules.features.poe2.live_terrain.terrain_reference import TerrainReference

from .models import CandidateRegion, MultiFrameEvidence, PositionEstimate


SCHEMA_VERSION = 3
COORDINATE_SPACE = "native"


@dataclass(frozen=True)
class MultiframeReplayBundle:
    evidence: tuple[MultiFrameEvidence, ...]
    anchor: PositionAnchor
    reference: TerrainReference
    instance_id: str
    estimate: PositionEstimate | None
    diagnostics: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence", tuple(self.evidence))
        object.__setattr__(self, "diagnostics", MappingProxyType(dict(self.diagnostics)))


def _json_value(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


class MultiframeArchive:
    """Publish a replay bundle only after every payload has been written."""

    def save(
        self,
        directory: str | Path,
        *,
        evidence: tuple[MultiFrameEvidence, ...],
        anchor: PositionAnchor,
        instance_id: str,
        reference: TerrainReference,
        estimate: PositionEstimate | None = None,
        diagnostics: Mapping[str, Any] | None = None,
    ) -> Path:
        if not isinstance(anchor, PositionAnchor):
            raise TypeError("anchor must be PositionAnchor")
        evidence = tuple(evidence)
        if not evidence:
            raise ValueError("cannot archive an empty evidence window")
        if not instance_id or anchor.area_instance != str(instance_id):
            raise ValueError("archive anchor and instance must match")
        if not isinstance(reference, TerrainReference):
            raise TypeError("reference must be TerrainReference")
        if str(reference.metadata.get("instance_id") or instance_id) != str(instance_id):
            raise ValueError("archive reference and instance must match")
        target = Path(directory)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise FileExistsError(f"archive target already exists: {target}")
        temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.tmp-", dir=target.parent))
        try:
            arrays: dict[str, np.ndarray] = {}
            arrays["reference_walkable"] = np.asarray(reference.walkable_mask, dtype=np.uint8)
            arrays["reference_wall"] = np.asarray(reference.wall_layer, dtype=np.uint8)
            arrays["reference_explored"] = np.asarray(reference.explored_map, dtype=np.uint8)
            manifest: dict[str, Any] = {
                "schema_version": SCHEMA_VERSION,
                "coordinate_space": COORDINATE_SPACE,
                "instance_id": str(instance_id),
                "anchor": {
                    "position": list(anchor.position),
                    "area_instance": anchor.area_instance,
                    "captured_at_ms": anchor.captured_at_ms,
                    "source": anchor.source,
                    "confidence": anchor.confidence,
                },
                "reference": {
                    "width": reference.width,
                    "height": reference.height,
                    "walkable_key": "reference_walkable",
                    "wall_key": "reference_wall",
                    "explored_key": "reference_explored",
                    "metadata": _json_value(reference.metadata),
                },
                "frame_ids": [],
                "frames": [],
                "estimate": None,
                "diagnostics": _json_value(dict(diagnostics or {})),
            }
            for item in evidence:
                frame_id = item.frame.frame_id
                wall_key = f"wall_{frame_id}"
                observed_key = f"observed_{frame_id}"
                arrays[wall_key] = np.asarray(item.frame.wall_mask, dtype=np.uint8)
                arrays[observed_key] = np.asarray(item.observed_mask, dtype=np.uint8)
                raw_key = None
                if item.raw_frame is not None:
                    raw_key = f"raw_{frame_id}"
                    arrays[raw_key] = np.asarray(item.raw_frame)
                manifest["frame_ids"].append(frame_id)
                manifest["frames"].append({
                    "frame_id": frame_id,
                    "captured_at_ms": item.frame.captured_at_ms,
                    "wall_key": wall_key,
                    "observed_key": observed_key,
                    "raw_key": raw_key,
                    "local_player": list(item.frame.local_player),
                    "offset": list(item.local_offset),
                    "keyframe": item.is_keyframe,
                    "segment_id": item.segment_id,
                    "frame_diagnostics": _json_value(item.frame.diagnostics),
                    "motion": {
                        "shift": item.motion.shift,
                        "quality": item.motion.quality,
                        "distance": item.motion.distance,
                        "accepted": item.motion.accepted,
                        "reason": item.motion.reason,
                    },
                })
            if estimate is not None:
                manifest["estimate"] = {
                    "status": estimate.status,
                    "position": estimate.position,
                    "velocity": estimate.velocity,
                    "covariance": _json_value(estimate.covariance),
                    "candidate_regions": [
                        {
                            "position": region.position,
                            "score": region.score,
                            "support_frames": region.support_frames,
                            "covariance": _json_value(region.covariance),
                            "transform": {
                                "angle_degrees": region.transform.angle_degrees,
                                "reflect_horizontal": region.transform.reflect_horizontal,
                                "scale": region.transform.scale,
                                "translation": region.transform.translation,
                            },
                        }
                        for region in estimate.candidate_regions
                    ],
                    "instance_id": estimate.instance_id,
                    "registration_version": estimate.registration_version,
                    "evidence_version": estimate.evidence_version,
                    "fresh": estimate.fresh,
                    "age_ms": estimate.age_ms,
                    "source": estimate.source,
                    "reason": estimate.reason,
                    "diagnostics": _json_value(estimate.diagnostics),
                }
            np.savez_compressed(temporary / "evidence.npz", **arrays)
            (temporary / "manifest.json").write_text(
                json.dumps(_json_value(manifest), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(temporary, target)
        except Exception:
            shutil.rmtree(temporary, ignore_errors=True)
            raise
        return target

    def load(self, directory: str | Path) -> MultiframeReplayBundle:
        source = Path(directory).expanduser().resolve()
        manifest_path = source / "manifest.json"
        arrays_path = source / "evidence.npz"
        if not manifest_path.is_file():
            raise ValueError("multiframe archive manifest is missing")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict) or manifest.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("unsupported multiframe archive schema")
        if manifest.get("coordinate_space") != COORDINATE_SPACE:
            raise ValueError("multiframe archive must use native coordinates")
        if not arrays_path.is_file():
            raise ValueError("multiframe archive evidence is missing")
        anchor_payload = manifest.get("anchor")
        if not isinstance(anchor_payload, dict):
            raise ValueError("multiframe archive anchor is missing")
        anchor = PositionAnchor(
            tuple(anchor_payload["position"]),
            str(anchor_payload["area_instance"]),
            int(anchor_payload["captured_at_ms"]),
            str(anchor_payload["source"]),
            float(anchor_payload.get("confidence", 1.0)),
        )
        instance_id = str(manifest.get("instance_id") or "")
        if not instance_id or anchor.area_instance != instance_id:
            raise ValueError("multiframe archive instance does not match anchor")
        frames_payload = manifest.get("frames")
        if not isinstance(frames_payload, list):
            raise ValueError("multiframe archive frames are missing")
        evidence: list[MultiFrameEvidence] = []
        estimate_payload = manifest.get("estimate")
        estimate = None
        if estimate_payload is not None:
            if not isinstance(estimate_payload, dict):
                raise ValueError("multiframe archive estimate is invalid")
            if str(estimate_payload.get("instance_id") or "") != instance_id:
                raise ValueError("multiframe archive estimate does not match instance")
            regions_payload = estimate_payload.get("candidate_regions", [])
            if not isinstance(regions_payload, list):
                raise ValueError("multiframe archive candidate regions are invalid")
            regions: list[CandidateRegion] = []
            for region_payload in regions_payload:
                if not isinstance(region_payload, dict):
                    raise ValueError("multiframe archive candidate region is invalid")
                transform_payload = region_payload.get("transform")
                if not isinstance(transform_payload, dict):
                    raise ValueError("multiframe archive candidate transform is missing")
                transform = SimilarityTransform2D(
                    float(transform_payload["angle_degrees"]),
                    bool(transform_payload["reflect_horizontal"]),
                    float(transform_payload["scale"]),
                    tuple(transform_payload["translation"]),
                )
                regions.append(
                    CandidateRegion(
                        transform,
                        tuple(region_payload["position"]),
                        region_payload.get("covariance"),
                        float(region_payload["score"]),
                        tuple(region_payload.get("support_frames", ())),
                    )
                )
            estimate = PositionEstimate(
                status=str(estimate_payload["status"]),
                position=estimate_payload.get("position"),
                velocity=estimate_payload.get("velocity"),
                covariance=estimate_payload.get("covariance"),
                candidate_regions=tuple(regions),
                instance_id=instance_id,
                registration_version=int(estimate_payload["registration_version"]),
                evidence_version=int(estimate_payload["evidence_version"]),
                fresh=bool(estimate_payload["fresh"]),
                age_ms=int(estimate_payload["age_ms"]),
                source=str(estimate_payload["source"]),
                reason=str(estimate_payload["reason"]),
                diagnostics=dict(estimate_payload.get("diagnostics") or {}),
            )
        with np.load(arrays_path, allow_pickle=False) as arrays:
            reference_payload = manifest.get("reference")
            if not isinstance(reference_payload, dict):
                raise ValueError("multiframe archive reference is missing")
            reference = TerrainReference(
                np.asarray(arrays[str(reference_payload["walkable_key"])]),
                np.asarray(arrays[str(reference_payload["wall_key"])]),
                np.asarray(arrays[str(reference_payload["explored_key"])]),
                int(reference_payload["width"]),
                int(reference_payload["height"]),
                dict(reference_payload.get("metadata") or {}),
            )
            for item in frames_payload:
                if not isinstance(item, dict):
                    raise ValueError("multiframe archive frame is invalid")
                wall = np.asarray(arrays[str(item["wall_key"])])
                observed = np.asarray(arrays[str(item["observed_key"])])
                raw_key = item.get("raw_key")
                raw = None if raw_key is None else np.asarray(arrays[str(raw_key)])
                frame = HybridFrame(
                    int(item["frame_id"]),
                    int(item["captured_at_ms"]),
                    wall,
                    tuple(item["local_player"]),
                    dict(item.get("frame_diagnostics") or {}),
                )
                motion_payload = item.get("motion") or {}
                shift_payload = motion_payload.get("shift")
                if shift_payload is None:
                    shift = None
                else:
                    if not isinstance(shift_payload, (list, tuple)) or len(shift_payload) != 2:
                        raise ValueError("multiframe archive motion shift must contain two values")
                    shift = float(shift_payload[0]), float(shift_payload[1])
                    if not np.isfinite(shift).all():
                        raise ValueError("multiframe archive motion shift must be finite")
                motion = FrameDisplacement(
                    shift,
                    float(motion_payload.get("quality", 0.0)),
                    float(motion_payload.get("distance", 0.0)),
                    bool(motion_payload.get("accepted", False)),
                    str(motion_payload.get("reason", "")),
                )
                evidence.append(
                    MultiFrameEvidence(
                        frame,
                        motion,
                        tuple(item["offset"]),
                        bool(item.get("keyframe", False)),
                        int(item.get("segment_id", 0)),
                        observed,
                        raw,
                    )
                )
        return MultiframeReplayBundle(
            tuple(evidence),
            anchor,
            reference,
            instance_id,
            estimate,
            dict(manifest.get("diagnostics") or {}),
        )


__all__ = [
    "COORDINATE_SPACE",
    "MultiframeArchive",
    "MultiframeReplayBundle",
    "SCHEMA_VERSION",
]
