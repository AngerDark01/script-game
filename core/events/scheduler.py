from __future__ import annotations

import math

from .models import EventTaskState


class EventScheduler:
    def pick(self, tasks: list, player_global_pos=None):
        running = [task for task in tasks if task.state == EventTaskState.RUNNING]
        if running:
            return running[0]

        pending = [task for task in tasks if task.state == EventTaskState.PENDING]
        if not pending:
            return None

        def sort_key(task):
            distance = 0.0
            if player_global_pos is not None:
                distance = math.hypot(
                    float(task.global_pos[0]) - float(player_global_pos[0]),
                    float(task.global_pos[1]) - float(player_global_pos[1]),
                )
            return (-int(task.priority), distance, int(task.first_seen_ms))

        return sorted(pending, key=sort_key)[0]

