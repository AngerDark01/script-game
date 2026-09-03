from __future__ import annotations

import cv2

from core.events.detectors.template_matcher import TemplateSpec

from .masks import portal_blue_mask, portal_outer_mask, resize_image, resize_mask
from .models import PortalShapeColorParams, PreparedShapeColorTemplate


def prepare_shape_color_template(
    template: TemplateSpec,
    scale: float,
    params: PortalShapeColorParams,
) -> PreparedShapeColorTemplate:
    image = resize_image(template.image, scale)
    blue = portal_blue_mask(
        image,
        hue_min=params.hue_min,
        hue_max=params.hue_max,
        sat_min=params.sat_min,
        val_min=params.val_min,
    )
    outer = portal_outer_mask(
        image,
        sat_max=params.outer_sat_max,
        val_min=params.outer_val_min,
        blue_mask=blue,
    )
    shape = cv2.bitwise_or(blue, outer)
    if template.mask is not None:
        alpha = resize_mask(template.mask, scale)
        blue = cv2.bitwise_and(blue, alpha)
        outer = cv2.bitwise_and(outer, alpha)
        shape = cv2.bitwise_and(shape, alpha)
    edge = cv2.Canny(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), 50, 150)
    return PreparedShapeColorTemplate(
        name=template.name,
        scale=float(scale),
        image=image,
        blue_mask=blue,
        outer_mask=outer,
        shape_mask=shape,
        edge_mask=edge,
    )
