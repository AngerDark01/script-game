import unittest

from core.perception.models import CoordinateSpace
from core.spatial.calibration import CoordinateMapper, fit_affine_transform
from core.spatial.models import CoordinateAnchor, Point2D, WindowRect


class SpatialCalibrationTests(unittest.TestCase):
    def test_affine_transform_maps_points_from_three_anchors(self):
        anchors = (
            CoordinateAnchor(Point2D(0, 0), Point2D(100, 50)),
            CoordinateAnchor(Point2D(10, 0), Point2D(120, 50)),
            CoordinateAnchor(Point2D(0, 10), Point2D(100, 75)),
        )

        transform = fit_affine_transform(anchors)

        mapped = transform.map_point(Point2D(4, 8))
        self.assertAlmostEqual(108.0, mapped.x, places=5)
        self.assertAlmostEqual(70.0, mapped.y, places=5)

    def test_mapper_requires_registered_transform_for_non_identity_spaces(self):
        mapper = CoordinateMapper()
        point = Point2D(2, 3)

        with self.assertRaises(KeyError):
            mapper.map(point, CoordinateSpace.VIEWPORT, CoordinateSpace.FULL_SCREEN)

        mapper.register(
            CoordinateSpace.VIEWPORT,
            CoordinateSpace.FULL_SCREEN,
            fit_affine_transform(
                (
                    CoordinateAnchor(Point2D(0, 0), Point2D(10, 20)),
                    CoordinateAnchor(Point2D(1, 0), Point2D(12, 20)),
                    CoordinateAnchor(Point2D(0, 1), Point2D(10, 23)),
                )
            ),
        )
        mapped = mapper.map(point, CoordinateSpace.VIEWPORT, CoordinateSpace.FULL_SCREEN)
        self.assertAlmostEqual(14.0, mapped.x, places=5)
        self.assertAlmostEqual(29.0, mapped.y, places=5)

    def test_window_rect_converts_normalized_points_to_screen_pixels(self):
        window = WindowRect(left=100, top=200, width=800, height=600)

        self.assertEqual(Point2D(500.0, 350.0), window.from_normalized(Point2D(0.5, 0.25)))

    def test_affine_fit_rejects_collinear_anchors(self):
        with self.assertRaises(ValueError):
            fit_affine_transform(
                (
                    CoordinateAnchor(Point2D(0, 0), Point2D(0, 0)),
                    CoordinateAnchor(Point2D(1, 1), Point2D(1, 1)),
                    CoordinateAnchor(Point2D(2, 2), Point2D(2, 2)),
                )
            )


if __name__ == "__main__":
    unittest.main()
