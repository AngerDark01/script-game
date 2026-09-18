import json
from pathlib import Path


class RouteManager:
    """Persist per-map route data for auto navigation."""

    def __init__(self):
        self._cache = {}

    def _route_path(self, map_folder) -> Path:
        return Path(map_folder) / "route.json"

    def _default_data(self) -> dict:
        return {
            "version": 1,
            "routes": {
                "main": {
                    "exit_region": None,
                    "required_points": [],
                    "guide_points": [],
                }
            },
        }

    def load_route(self, map_folder, force_reload: bool = False) -> dict:
        path = self._route_path(map_folder)
        cache_key = str(path)
        if not force_reload and cache_key in self._cache:
            return self._cache[cache_key]

        if not path.exists():
            data = self._default_data()
            self._cache[cache_key] = data
            return data

        try:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            data = self._default_data()

        if "routes" not in data or "main" not in data["routes"]:
            data = self._default_data()
        else:
            main = data["routes"]["main"]
            main.setdefault("exit_region", None)
            main.setdefault("required_points", [])
            main.setdefault("guide_points", [])

        self._cache[cache_key] = data
        return data

    def save_route(self, map_folder) -> bool:
        path = self._route_path(map_folder)
        cache_key = str(path)
        data = self._cache.setdefault(cache_key, self._default_data())
        try:
            with path.open("w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
            return True
        except OSError:
            return False

    def get_main_route(self, map_folder) -> dict:
        return self.load_route(map_folder)["routes"]["main"]

    def set_exit_region(self, map_folder, center, radius: int = 28) -> dict:
        route = self.get_main_route(map_folder)
        route["exit_region"] = {
            "center": [int(center[0]), int(center[1])],
            "radius": int(radius),
        }
        return route

    def clear_exit_region(self, map_folder) -> dict:
        route = self.get_main_route(map_folder)
        route["exit_region"] = None
        return route

    def add_guide_point(self, map_folder, point) -> list:
        route = self.get_main_route(map_folder)
        route["guide_points"].append([int(point[0]), int(point[1])])
        return route["guide_points"]

    def add_required_point(self, map_folder, point) -> list:
        route = self.get_main_route(map_folder)
        route["required_points"].append([int(point[0]), int(point[1])])
        return route["required_points"]

    def undo_guide_point(self, map_folder) -> list:
        route = self.get_main_route(map_folder)
        if route["guide_points"]:
            route["guide_points"].pop()
        return route["guide_points"]

    def undo_required_point(self, map_folder) -> list:
        route = self.get_main_route(map_folder)
        if route["required_points"]:
            route["required_points"].pop()
        return route["required_points"]

    def clear_route(self, map_folder) -> dict:
        route = self.get_main_route(map_folder)
        route["exit_region"] = None
        route["required_points"] = []
        route["guide_points"] = []
        return route
