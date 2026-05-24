from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.navigation_tasks.route_context import RouteContext


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--map", default="Aa", dest="map_name")
    args = parser.parse_args()

    route_path = ROOT / "map_data" / args.map_name / "route.json"
    with route_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    route = data.get("routes", {}).get("main", {})
    context = RouteContext(route.get("guide_points", []))

    for anchor in context.anchors:
        x, y = anchor.point
        print(f"guide[{anchor.index}] pos=({int(x)}, {int(y)}) progress={anchor.progress:.2f}")
    for index, point in enumerate(route.get("required_points", [])):
        progress = context.progress_of(point)
        print(f"required[{index}] pos=({point[0]}, {point[1]}) progress={progress:.2f}")
    exit_region = route.get("exit_region")
    if exit_region:
        progress = context.progress_of(exit_region["center"])
        print(f"exit pos=({exit_region['center'][0]}, {exit_region['center'][1]}) progress={progress:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
