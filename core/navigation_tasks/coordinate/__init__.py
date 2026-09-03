"""Coordinate diagnostics helper package."""

from .diagnostics import (
    CoordinateDiagnostics,
    _distance,
    _float_point_or_none,
    _format_fields,
    _format_value,
    _registration_fields,
)
from .formatting import distance, float_point_or_none, format_fields, format_value, registration_fields
from .localization import (
    is_f2f_registration,
    record_localization_diagnostics,
    record_visual_consistency,
    track_registration_source,
)
from .log import coord_log
from .models import CoordinateRelocalizationRequest
from .navigation import record_navigation_diagnostics
from .relocalization import (
    check_active_relocalization,
    consume_relocalization_request,
    mark_relocalization_accepted,
    register_recovery_signal,
    should_request_relocalization,
)

__all__ = [
    "CoordinateDiagnostics",
    "CoordinateRelocalizationRequest",
    "_distance",
    "_float_point_or_none",
    "_format_fields",
    "_format_value",
    "_registration_fields",
    "check_active_relocalization",
    "consume_relocalization_request",
    "coord_log",
    "distance",
    "float_point_or_none",
    "format_fields",
    "format_value",
    "is_f2f_registration",
    "mark_relocalization_accepted",
    "record_localization_diagnostics",
    "record_navigation_diagnostics",
    "record_visual_consistency",
    "register_recovery_signal",
    "registration_fields",
    "should_request_relocalization",
    "track_registration_source",
]
