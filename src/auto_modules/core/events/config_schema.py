"""Helpers for domain-neutral event configuration schema metadata."""

from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy


def with_display_hints(
    schema: dict,
    *,
    compact: Iterable[str] = (),
    summary: Iterable[str] = (),
) -> dict:
    """Copy a config schema and mark fields for compact and summary surfaces."""
    result = deepcopy(schema)
    compact_keys = set(compact)
    summary_keys = set(summary)
    unknown = (compact_keys | summary_keys) - set(result)
    if unknown:
        raise ValueError(f"display hints reference unknown config fields: {sorted(unknown)}")
    for key in compact_keys:
        result[key]["compact"] = True
    for key in summary_keys:
        result[key]["summary"] = True
    return result


__all__ = ["with_display_hints"]
