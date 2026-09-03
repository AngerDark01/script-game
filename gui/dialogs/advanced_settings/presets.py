from __future__ import annotations

from types import MappingProxyType
from typing import Mapping


DEFAULT_PRESET_NAME = "默认参数"
PRESET_NAMES = (
    DEFAULT_PRESET_NAME,
    "流放之路优化",
    "火炬之光优化",
    "高对比度模式",
    "低对比度模式",
)

_PRESET_VALUES: dict[str, dict[str, float | int]] = {
    "流放之路优化": {
        "contrast_factor_spin": 1.3,
        "blue_boost_spin": 1.2,
        "edge_low_spin": 40,
        "edge_high_spin": 120,
        "wall_weight_spin": 60,
        "edge_weight_spin": 25,
        "gray_weight_spin": 15,
    },
    "火炬之光优化": {
        "contrast_factor_spin": 1.1,
        "blue_boost_spin": 1.0,
        "edge_low_spin": 60,
        "edge_high_spin": 180,
        "wall_weight_spin": 45,
        "edge_weight_spin": 35,
        "gray_weight_spin": 20,
    },
    "高对比度模式": {
        "contrast_factor_spin": 1.5,
        "blue_boost_spin": 1.3,
        "clahe_clip_spin": 3.0,
    },
    "低对比度模式": {
        "contrast_factor_spin": 1.0,
        "blue_boost_spin": 1.0,
        "clahe_clip_spin": 1.5,
    },
}

PRESET_VALUES: Mapping[str, Mapping[str, float | int]] = MappingProxyType(
    {name: MappingProxyType(values) for name, values in _PRESET_VALUES.items()}
)


def preset_names() -> tuple[str, ...]:
    return PRESET_NAMES


def preset_values(preset: str) -> Mapping[str, float | int] | None:
    return PRESET_VALUES.get(preset)
