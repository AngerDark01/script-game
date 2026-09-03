from __future__ import annotations

import numpy as np

from core.events.detectors.template_matcher import TemplateSpec

from .masks import portal_blue_mask
from .models import PortalFeatureTemplate


def build_feature_templates(
    templates: list[TemplateSpec],
    *,
    hue_min: int = 82,
    hue_max: int = 136,
    sat_min: int = 55,
    val_min: int = 95,
    min_template_pixels: int = 8,
) -> list[PortalFeatureTemplate]:
    feature_templates: list[PortalFeatureTemplate] = []
    for template in templates:
        mask = portal_blue_mask(
            template.image,
            hue_min=hue_min,
            hue_max=hue_max,
            sat_min=sat_min,
            val_min=val_min,
        )
        if int(np.count_nonzero(mask)) < int(min_template_pixels):
            continue
        feature_templates.append(PortalFeatureTemplate(name=template.name, mask=mask))
    return feature_templates
