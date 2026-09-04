import unittest

from core.perception.models import CoordinateSpace
from core.spatial import Point2D
from core.spatial.desktop_mapping import DesktopCoordinateMapper, ScreenGeometry


class DesktopCoordinateMapperTests(unittest.TestCase):
    def test_frame_center_maps_by_scale_and_desktop_offset(self):
        mapper = DesktopCoordinateMapper(
            source_size=(1920, 1080),
            destination=ScreenGeometry(left=-1920, top=0, width=3840, height=2160),
        )

        mapped = mapper.map_point(Point2D(960, 540), CoordinateSpace.FULL_SCREEN)

        self.assertEqual(Point2D(0, 1080), mapped.destination_point)
        self.assertEqual(Point2D(960, 540), mapped.source_point)
        self.assertEqual(CoordinateSpace.FULL_SCREEN, mapped.source_space)
        self.assertEqual(CoordinateSpace.PHYSICAL_SCREEN, mapped.destination_space)
        self.assertEqual(2.0, mapped.metadata["scale_x"])
        self.assertEqual(2.0, mapped.metadata["scale_y"])
        self.assertEqual("scale_offset", mapped.metadata["transform"])


if __name__ == "__main__":
    unittest.main()
