from __future__ import annotations


def map_to_grid(pos, downsample_factor: int) -> tuple[int, int]:
    """Convert map-space coordinates to downsampled grid coordinates."""
    factor = max(1, int(downsample_factor))
    return (int(pos[0] / factor), int(pos[1] / factor))


def grid_size_from_map_shape(shape, downsample_factor: int) -> tuple[int, int]:
    """Return a complete downsampled grid size as ``(width, height)``.

    ``ceil`` is intentional: a native map whose width/height is not an exact
    multiple of the downsample factor still has a valid border corridor.  The
    previous floor conversion silently discarded that strip, which could make
    a target near the edge appear unreachable or force a route through a
    neighbouring wall cell.
    """
    import math

    h, w = shape[:2]
    factor = max(1, int(downsample_factor))
    return max(1, math.ceil(w / factor)), max(1, math.ceil(h / factor))


def in_grid_bounds(grid_pos, grid_w: int, grid_h: int) -> bool:
    """Return whether a grid coordinate is inside the downsampled map."""
    return 0 <= grid_pos[0] < grid_w and 0 <= grid_pos[1] < grid_h


def grid_path_to_map_path(path_grid, downsample_factor: int, end_pos) -> list[tuple[int, int]]:
    """Convert grid path cells back to map-space center points."""
    factor = max(1, int(downsample_factor))
    path_global = [
        (int(px * factor + factor / 2), int(py * factor + factor / 2))
        for px, py in path_grid
    ]
    if path_global and path_global[-1] != end_pos:
        path_global.append(end_pos)
    return path_global
