from __future__ import annotations

from dataclasses import dataclass

from auto_modules.core.localization import LocalizationResult


@dataclass(frozen=True)
class NavigationLocalizationResult:
    global_x: float | None
    global_y: float | None
    confidence: float

    @property
    def localized_pos(self) -> tuple[float, float] | None:
        if self.global_x is None or self.global_y is None:
            return None
        return self.global_x, self.global_y

    @property
    def is_localized(self) -> bool:
        return self.localized_pos is not None

    @classmethod
    def from_core_result(cls, result) -> "NavigationLocalizationResult":
        if isinstance(result, LocalizationResult):
            global_x, global_y, confidence = result.as_legacy_tuple()
            return cls(global_x=global_x, global_y=global_y, confidence=confidence)
        global_x, global_y, confidence = result
        return cls(global_x=global_x, global_y=global_y, confidence=confidence)
