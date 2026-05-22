import tempfile
import unittest
from pathlib import Path

from core.route_manager import RouteManager


class RouteManagerTest(unittest.TestCase):
    def test_missing_route_file_returns_empty_default(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = RouteManager()
            data = manager.load_route(Path(temp_dir))
            self.assertEqual(data["routes"]["main"]["guide_points"], [])
            self.assertEqual(data["routes"]["main"]["required_points"], [])
            self.assertIsNone(data["routes"]["main"]["exit_region"])

    def test_save_and_reload_route_round_trip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            manager = RouteManager()
            manager.set_exit_region(folder, (100, 200), 25)
            manager.add_required_point(folder, (5, 15))
            manager.add_guide_point(folder, (10, 20))
            manager.add_guide_point(folder, (30, 40))
            self.assertTrue(manager.save_route(folder))

            reloaded = RouteManager()
            data = reloaded.load_route(folder, force_reload=True)
            main = data["routes"]["main"]
            self.assertEqual(main["exit_region"]["center"], [100, 200])
            self.assertEqual(main["exit_region"]["radius"], 25)
            self.assertEqual(main["required_points"], [[5, 15]])
            self.assertEqual(main["guide_points"], [[10, 20], [30, 40]])

    def test_undo_required_point_removes_only_required_points(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            manager = RouteManager()
            manager.add_required_point(folder, (5, 15))
            manager.add_required_point(folder, (6, 16))
            manager.add_guide_point(folder, (10, 20))

            self.assertEqual(manager.undo_required_point(folder), [[5, 15]])
            main = manager.get_main_route(folder)
            self.assertEqual(main["required_points"], [[5, 15]])
            self.assertEqual(main["guide_points"], [[10, 20]])


if __name__ == "__main__":
    unittest.main()
