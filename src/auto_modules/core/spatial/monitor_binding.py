"""Device-neutral monitor rectangle contracts."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class CaptureRect:
    left: int
    top: int
    width: int
    height: int

    def __post_init__(self) -> None:
        if int(self.width) <= 0 or int(self.height) <= 0:
            raise ValueError("capture rectangle dimensions must be positive")
        object.__setattr__(self, "left", int(self.left))
        object.__setattr__(self, "top", int(self.top))
        object.__setattr__(self, "width", int(self.width))
        object.__setattr__(self, "height", int(self.height))

    def as_dict(self) -> dict[str, int]:
        return {"left": self.left, "top": self.top, "width": self.width, "height": self.height}


@dataclass(frozen=True)
class MonitorBinding:
    rect: CaptureRect
    screen_id: str = "primary"
    coordinate_space: str = "physical_desktop"
    dpi_scale_x: float = 1.0
    dpi_scale_y: float = 1.0
    player_marker_position: tuple[int, int] | None = None

    def __post_init__(self) -> None:
        if not self.screen_id:
            raise ValueError("screen_id is required")
        if not isfinite(float(self.dpi_scale_x)) or not isfinite(float(self.dpi_scale_y)):
            raise ValueError("dpi scales must be finite")
        if self.dpi_scale_x <= 0 or self.dpi_scale_y <= 0:
            raise ValueError("dpi scales must be positive")
        marker = self.player_marker_position
        if marker is not None:
            if len(marker) != 2 or not all(isinstance(item, int) for item in marker):
                raise ValueError("player_marker_position must contain two integers")
            if not (0 <= marker[0] < self.rect.width and 0 <= marker[1] < self.rect.height):
                raise ValueError("player_marker_position must be inside the capture rectangle")
            object.__setattr__(self, "player_marker_position", (int(marker[0]), int(marker[1])))

    def as_dict(self) -> dict:
        return {
            "rect": self.rect.as_dict(),
            "screen_id": self.screen_id,
            "coordinate_space": self.coordinate_space,
            "dpi_scale_x": float(self.dpi_scale_x),
            "dpi_scale_y": float(self.dpi_scale_y),
            "player_marker_position": list(self.player_marker_position)
            if self.player_marker_position is not None
            else None,
        }


def resize_binding_around_marker(
    binding: MonitorBinding,
    width: int,
    height: int,
) -> MonitorBinding:
    """Resize a capture while keeping its marker at the same desktop point."""
    width = int(width)
    height = int(height)
    if width <= 0 or height <= 0:
        raise ValueError("capture rectangle dimensions must be positive")
    marker = binding.player_marker_position
    if marker is None:
        marker = (binding.rect.width // 2, binding.rect.height // 2)
    anchor = (
        binding.rect.left + int(marker[0]),
        binding.rect.top + int(marker[1]),
    )
    new_marker = (width // 2, height // 2)
    return MonitorBinding(
        rect=CaptureRect(
            anchor[0] - new_marker[0],
            anchor[1] - new_marker[1],
            width,
            height,
        ),
        screen_id=binding.screen_id,
        coordinate_space=binding.coordinate_space,
        dpi_scale_x=binding.dpi_scale_x,
        dpi_scale_y=binding.dpi_scale_y,
        player_marker_position=new_marker,
    )


__all__ = ["CaptureRect", "MonitorBinding", "resize_binding_around_marker"]
