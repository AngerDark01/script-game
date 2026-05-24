from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.navigation_tasks.route_context import RouteContext
from core.navigation_tasks.task_builder import NavigationTaskBuilder


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--map", default="Aa", dest="map_name")
    args = parser.parse_args()

    route_path = ROOT / "map_data" / args.map_name / "route.json"
    with route_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    route = data.get("routes", {}).get("main", {})
    context = RouteContext(route.get("guide_points", []))
    tasks = NavigationTaskBuilder().build(
        route=route,
        event_tasks=[],
        route_context=context,
        completed_required=set(),
    )
    for task in tasks:
        x, y = task.target_pos
        progress = "none" if task.route_progress is None else f"{task.route_progress:.2f}"
        print(f"{task.id} kind={task.kind.value} target=({int(x)}, {int(y)}) progress={progress}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
