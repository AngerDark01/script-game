"""Portal minimap shape-color matcher helper package."""

from .masks import portal_blue_mask, portal_outer_mask, resize_image, resize_mask, to_bgr, to_hsv
from .models import (
    PortalShapeColorDebug,
    PortalShapeColorHit,
    PortalShapeColorParams,
    PreparedShapeColorTemplate,
)
from .pipeline import match_portal_shape_color, merge_shape_color_hits
from .scoring import (
    color_response_map,
    combined_shape_color_response,
    evaluate_shape_color_candidate,
    f1_score,
    mask_response,
    patch_color_score,
    response_hits,
)
from .templates import prepare_shape_color_template

__all__ = [
    "PortalShapeColorDebug",
    "PortalShapeColorHit",
    "PortalShapeColorParams",
    "PreparedShapeColorTemplate",
    "color_response_map",
    "combined_shape_color_response",
    "evaluate_shape_color_candidate",
    "f1_score",
    "mask_response",
    "match_portal_shape_color",
    "merge_shape_color_hits",
    "patch_color_score",
    "portal_blue_mask",
    "portal_outer_mask",
    "prepare_shape_color_template",
    "resize_image",
    "resize_mask",
    "response_hits",
    "to_bgr",
    "to_hsv",
]
