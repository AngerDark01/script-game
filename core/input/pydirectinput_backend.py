"""Lazy resolver for the optional pydirectinput fallback backend."""

from __future__ import annotations


def get_pydirectinput():
    """Import the backend only at the point a pydirectinput action is requested."""
    try:
        import pydirectinput
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "pydirectinput is required only for pydirectinput keyboard or mouse actions"
        ) from exc
    return pydirectinput
