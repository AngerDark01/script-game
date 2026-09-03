from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class LootTemplate:
    name: str
    image: np.ndarray
    mask: np.ndarray


@dataclass
class LootPreparedTemplate:
    name: str
    scale: float
    image: np.ndarray
    mask: np.ndarray
    gray: np.ndarray
    edges: np.ndarray
    edge_pixels: int
    mask_pixels: int


@dataclass
class LootCandidate:
    score: float
    template_score: float
    shape_score: float
    color_score: float
    scale: float
    top_left: tuple[int, int]
    size: tuple[int, int]
    center: tuple[int, int]
    template_name: str
    color_pixels: int
    accepted: bool


@dataclass
class LootCluster:
    score: float
    template_score: float
    shape_score: float
    color_score: float
    center: tuple[int, int]
    bbox: tuple[int, int, int, int]
    candidates: int
    templates: list[str]
