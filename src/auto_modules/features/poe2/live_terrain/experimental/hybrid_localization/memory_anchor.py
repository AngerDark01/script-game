"""PoE2 adapter that exposes one validated memory position as an anchor."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Callable

from auto_modules.features.poe2.live_terrain.orientation import TerrainOrientation
from auto_modules.features.poe2.live_terrain.player_position import Poe2PlayerPositionSource

from .models import PositionAnchor


def parse_timestamp_ms(value: str, *, fallback: Callable[[], int]) -> int:
    text = str(value or "").strip()
    if not text:
        return int(fallback())
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp() * 1000)


class Poe2MemoryAnchorProvider:
    def __init__(
        self,
        source: Poe2PlayerPositionSource,
        orientation: TerrainOrientation,
        native_shape: tuple[int, int],
        clock_ms: Callable[[], int] | None = None,
    ) -> None:
        height, width = int(native_shape[0]), int(native_shape[1])
        if height <= 0 or width <= 0:
            raise ValueError("native_shape dimensions must be positive")
        self.source = source
        self.orientation = orientation
        self.native_shape = (height, width)
        self.clock_ms = clock_ms or (lambda: int(time.time() * 1000))
        self.read_count = 0

    def read_once(self, expected_instance_id: str) -> PositionAnchor:
        self.read_count += 1
        sample = self.source.read_once(expected_instance_id)
        return PositionAnchor(
            position=self.orientation.transform_point(sample.grid, self.native_shape),
            area_instance=sample.area_instance,
            captured_at_ms=parse_timestamp_ms(sample.captured_at, fallback=self.clock_ms),
            source="poe2_memory",
        )


__all__ = ["Poe2MemoryAnchorProvider", "parse_timestamp_ms"]
