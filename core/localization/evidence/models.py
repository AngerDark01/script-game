from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class VisualCheckEvidence:
    status: str = ""
    player: Any = None
    delta: Any = None
    delta_dist: float = 0.0
    confidence: float = 0.0
    expected_score: Any = None
    mismatch: bool = False

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    def exceeds_mismatch_threshold(self, threshold: float) -> bool:
        return self.ok and bool(self.mismatch) and self.delta_dist >= float(threshold)


@dataclass(frozen=True)
class LocalizationEvidence:
    raw_pos: tuple[float, float] | None
    trusted_pos: tuple[float, float] | None
    control_pos: tuple[float, float] | None
    confidence: float
    min_confidence: float
    registration_present: bool
    registration_valid: bool | None = None
    registration_source: str | None = None
    registration_confidence: float = 0.0
    registration_player: tuple[float, float] | None = None
    registration_local: Any = None
    registration_origin: tuple[float, float] | None = None
    registration_metadata: dict[str, Any] = field(default_factory=dict)
    visual: VisualCheckEvidence = field(default_factory=VisualCheckEvidence)

    @property
    def invalid_reason(self) -> str | None:
        if self.raw_pos is None:
            return "no_position"
        if self.confidence < self.min_confidence:
            return "low_confidence"
        return None

    @property
    def is_valid_position(self) -> bool:
        return self.invalid_reason is None

    @property
    def is_f2f(self) -> bool:
        return bool(self.registration_valid) and str(self.registration_source or "") == "f2f"

    @property
    def is_template_match(self) -> bool:
        return bool(self.registration_valid) and str(self.registration_source or "") == "template_match"

    @property
    def forced_global(self) -> bool:
        return bool(self.registration_metadata.get("forced_global"))

    @property
    def registration_fields(self) -> dict[str, Any]:
        if not self.registration_present:
            return {"reg_valid": None, "reg_source": None}
        return {
            "reg_valid": bool(self.registration_valid),
            "reg_source": self.registration_source or "",
            "reg_conf": float(self.registration_confidence or 0.0),
            "reg_player": self.registration_player,
            "reg_local": self.registration_local,
            "reg_origin": self.registration_origin,
            "reg_meta": self.registration_metadata,
        }
