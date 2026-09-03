from __future__ import annotations

from typing import Any, Mapping

from .algorithms.base import AlgorithmDescriptor, ParameterSpec
from .algorithms.color import ColorRegionDetector
from .algorithms.template import TemplateDetector
from .models import CoordinateSpace
from .registry import AlgorithmRegistry


def create_default_algorithm_registry() -> AlgorithmRegistry:
    """Return the algorithms exposed to profile editors and test tools."""
    registry = AlgorithmRegistry()
    registry.register(_color_descriptor(), _create_color)
    registry.register(_template_descriptor(), _create_template)
    for descriptor in (_shape_descriptor(), _feature_descriptor(), _ocr_descriptor()):
        registry.register(descriptor, None)
    return registry


def _create_color(parameters: Mapping[str, Any]) -> ColorRegionDetector:
    values = dict(parameters)
    target_type = str(values.pop("target_type", "target"))
    return ColorRegionDetector(target_type=target_type, parameters=values)


def _create_template(parameters: Mapping[str, Any]) -> TemplateDetector:
    values = dict(parameters)
    target_type = str(values.pop("target_type", "target"))
    template = values.pop("template", None) or values.pop("template_path", None)
    if template is None:
        raise ValueError("template algorithm requires a template or template_path")
    return TemplateDetector(target_type=target_type, template=template, parameters=values)


def _color_descriptor() -> AlgorithmDescriptor:
    return AlgorithmDescriptor(
        "color",
        "Color region",
        "Find connected regions selected by HSV bounds.",
        (CoordinateSpace.FULL_SCREEN, CoordinateSpace.GAME_WINDOW, CoordinateSpace.VIEWPORT),
        (
            ParameterSpec("hue_min", "Hue minimum", "int", 0, 0, 179),
            ParameterSpec("hue_max", "Hue maximum", "int", 179, 0, 179),
            ParameterSpec("saturation_min", "Saturation minimum", "int", 0, 0, 255),
            ParameterSpec("saturation_max", "Saturation maximum", "int", 255, 0, 255),
            ParameterSpec("value_min", "Value minimum", "int", 0, 0, 255),
            ParameterSpec("value_max", "Value maximum", "int", 255, 0, 255),
            ParameterSpec("min_area", "Minimum area", "float", 1.0, 0.0),
            ParameterSpec("max_area", "Maximum area", "float", 0.0, 0.0),
            ParameterSpec("morphology_kernel", "Morphology kernel", "int", 0, 0, 31),
        ),
    )


def _template_descriptor() -> AlgorithmDescriptor:
    return AlgorithmDescriptor(
        "template",
        "Masked template",
        "Multi-scale grayscale, edge, and optional alpha-mask matching.",
        (CoordinateSpace.FULL_SCREEN, CoordinateSpace.GAME_WINDOW, CoordinateSpace.VIEWPORT),
        (
            ParameterSpec("threshold", "Match threshold", "float", 0.75, 0.0, 1.0),
            ParameterSpec("top_k", "Maximum candidates", "int", 3, 1, 50),
            ParameterSpec("scales", "Scales", "text", "0.8,1.0,1.2"),
            ParameterSpec("edge_weight", "Edge weight", "float", 0.28, 0.0, 1.0),
            ParameterSpec("template_path", "Template path", "path", ""),
        ),
    )


def _shape_descriptor() -> AlgorithmDescriptor:
    return AlgorithmDescriptor(
        "shape",
        "Shape matching",
        "Reserved for contour and geometric matching.",
        (CoordinateSpace.FULL_SCREEN, CoordinateSpace.GAME_WINDOW, CoordinateSpace.VIEWPORT),
        status="unavailable",
    )


def _feature_descriptor() -> AlgorithmDescriptor:
    return AlgorithmDescriptor(
        "feature",
        "Feature matching",
        "Reserved for local feature and descriptor matching.",
        (CoordinateSpace.FULL_SCREEN, CoordinateSpace.GAME_WINDOW, CoordinateSpace.VIEWPORT),
        status="unavailable",
    )


def _ocr_descriptor() -> AlgorithmDescriptor:
    return AlgorithmDescriptor(
        "ocr",
        "OCR",
        "Reserved for an optional OCR provider.",
        (CoordinateSpace.FULL_SCREEN, CoordinateSpace.GAME_WINDOW, CoordinateSpace.VIEWPORT),
        status="unavailable",
    )
