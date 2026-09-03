from __future__ import annotations

import heapq


NEIGHBORS_8 = (
    (0, 1),
    (0, -1),
    (1, 0),
    (-1, 0),
    (1, 1),
    (1, -1),
    (-1, 1),
    (-1, -1),
)


def astar_path(grid, start, end):
    """Run 8-neighbor A* on an obstacle grid."""
    h, w = grid.shape

    open_set = []
    heapq.heappush(open_set, (0, start))

    came_from = {}
    g_score = {start: 0}
    f_score = {start: heuristic(start, end)}

    while open_set:
        current = heapq.heappop(open_set)[1]

        if current == end:
            return reconstruct_path(came_from, current)

        for dx, dy in NEIGHBORS_8:
            neighbor = (current[0] + dx, current[1] + dy)

            if not (0 <= neighbor[0] < w and 0 <= neighbor[1] < h):
                continue

            if grid[neighbor[1], neighbor[0]] > 0:
                continue

            if dx != 0 and dy != 0 and diagonal_cuts_corner(grid, current, dx, dy):
                continue

            move_cost = 1.414 if dx != 0 and dy != 0 else 1.0
            tentative_g_score = g_score[current] + move_cost

            if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g_score
                f_score[neighbor] = tentative_g_score + heuristic(neighbor, end)
                heapq.heappush(open_set, (f_score[neighbor], neighbor))

    return None


def diagonal_cuts_corner(grid, current, dx: int, dy: int) -> bool:
    """Reject diagonal motion through blocked orthogonal side cells."""
    side_a = (current[0] + dx, current[1])
    side_b = (current[0], current[1] + dy)
    return grid[side_a[1], side_a[0]] > 0 or grid[side_b[1], side_b[0]] > 0


def heuristic(a, b):
    """Manhattan distance heuristic."""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def reconstruct_path(came_from, current):
    """Reconstruct a path from the A* came_from map."""
    total_path = [current]
    while current in came_from:
        current = came_from[current]
        total_path.append(current)
    return total_path[::-1]
