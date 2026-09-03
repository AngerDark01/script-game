from __future__ import annotations


def find_nearest_walkable(grid, pos, max_radius: int):
    """Find the nearest walkable cell inside a Manhattan-radius scan."""
    h, w = grid.shape
    cx, cy = pos

    for radius in range(1, int(max_radius) + 1):
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if abs(dx) + abs(dy) > radius:
                    continue

                nx, ny = cx + dx, cy + dy
                if 0 <= nx < w and 0 <= ny < h and grid[ny, nx] == 0:
                    return (nx, ny)
    return None


def walkable_snap_grid_radius(walkable_snap_radius: int, downsample_factor: int) -> int:
    """Convert map-space snap radius to grid-space radius."""
    return max(
        1,
        int(round(int(walkable_snap_radius) / max(1, int(downsample_factor)))),
    )
