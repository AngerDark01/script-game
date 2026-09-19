"""PoE2 business policy for choosing one player from generic observations."""

from __future__ import annotations

from auto_modules.core.localization.observations import ObservationCandidate, ObservationFrame


def select_single_player(
    frame: ObservationFrame,
    *,
    min_confidence: float = 0.7,
) -> ObservationCandidate | None:
    """Return the only sufficiently confident candidate, or ``None``.

    Ambiguity is treated as a missing observation.  This prevents a single-
    player experiment from silently selecting another character when several
    markers are visible.
    """
    if not isinstance(frame, ObservationFrame):
        raise TypeError("frame must be an ObservationFrame")
    threshold = float(min_confidence)
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("min_confidence must be between 0 and 1")
    accepted = [candidate for candidate in frame.candidates if candidate.confidence >= threshold]
    return accepted[0] if len(accepted) == 1 else None


def select_single_player_frame(
    frame: ObservationFrame,
    *,
    min_confidence: float = 0.7,
) -> ObservationFrame:
    """Return a frame with an explicit selected index for runtime composition."""
    selected = select_single_player(frame, min_confidence=min_confidence)
    index = None
    if selected is not None:
        index = next(index for index, candidate in enumerate(frame.candidates) if candidate is selected)
    return ObservationFrame(
        captured_at_ms=frame.captured_at_ms,
        candidates=frame.candidates,
        selected_index=index,
        source=frame.source,
        stale=frame.stale,
    )


__all__ = ["select_single_player", "select_single_player_frame"]
