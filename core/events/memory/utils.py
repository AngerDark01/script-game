from __future__ import annotations

import math


def distance(a, b) -> float:
    return float(math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1])))


def int_pos(pos) -> tuple[int, int] | None:
    if pos is None:
        return None
    return int(pos[0]), int(pos[1])


def should_log(last_log_ms: dict[str, int], key: str, now_ms: int, interval_ms: int) -> bool:
    last_ms = last_log_ms.get(key)
    if last_ms is not None and now_ms - last_ms < interval_ms:
        return False
    last_log_ms[key] = int(now_ms)
    return True
