from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class FeaturePreparedTemplate:
    name: str
    kind: str
    scale: float
    image: np.ndarray
    mask: np.ndarray
    gray: np.ndarray
    edges: np.ndarray
    edge_mask: np.ndarray
    edge_distance: np.ndarray
    hog: np.ndarray
    body_contour: np.ndarray | None


@dataclass
class FeatureScore:
    score: float
    response_score: float
    template_score: float
    edge_score: float
    chamfer_score: float
    hog_score: float
    contour_score: float
    semantic_score: float
    color_score: float
    accepted: bool
    reject_reason: str
    metrics: dict[str, Any]
