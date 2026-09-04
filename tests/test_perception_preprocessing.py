import unittest

import numpy as np

from core.perception.models import BoundingBox, CoordinateSpace, FrameContext
from core.perception.preprocessing.geometry import crop, pad, resize
from core.perception.preprocessing.image_ops import (
    canny_edges,
    gamma_correct,
    gaussian_blur,
    lab_clahe,
    percentile_normalize,
    scale_bgr_channels,
    to_gray,
    to_hsv,
    top_hat,
)
from core.perception.preprocessing.models import ImageArtifact, ImageGeometry
from core.perception.preprocessing.masks import (
    circle_mask,
    filter_small_components,
    hsv_range_mask,
    intersect_masks,
    morphology,
    saturation_mask,
    subtract_mask,
    weighted_mask_fusion,
)


def make_artifact(*, width: int, height: int) -> ImageArtifact:
    frame = FrameContext(
        image=None,
        width=width,
        height=height,
        coordinate_space=CoordinateSpace.FULL_SCREEN,
    )
    return ImageArtifact(
        image=np.zeros((height, width), dtype=np.uint8),
        frame=frame,
        geometry=ImageGeometry.identity(
            width=width,
            height=height,
            coordinate_space=CoordinateSpace.FULL_SCREEN,
        ),
    )


class ImageGeometryTests(unittest.TestCase):
    def test_identity_geometry_keeps_point_and_box_in_source_frame(self):
        geometry = ImageGeometry.identity(
            width=100,
            height=80,
            coordinate_space=CoordinateSpace.FULL_SCREEN,
        )

        self.assertEqual((12.5, 20.0), geometry.map_point_to_source((12.5, 20.0)))
        self.assertEqual(
            BoundingBox(10, 15, 20, 10),
            geometry.map_box_to_source(BoundingBox(10, 15, 20, 10)),
        )

    def test_artifact_rejects_image_dimensions_that_disagree_with_geometry(self):
        frame = FrameContext(
            image=None,
            width=100,
            height=80,
            coordinate_space=CoordinateSpace.FULL_SCREEN,
        )
        geometry = ImageGeometry.identity(
            width=100,
            height=80,
            coordinate_space=CoordinateSpace.FULL_SCREEN,
        )

        with self.assertRaises(ValueError):
            ImageArtifact(
                image=np.zeros((79, 100), dtype=np.uint8),
                frame=frame,
                geometry=geometry,
            )

    def test_crop_resize_and_pad_map_back_to_original_coordinates(self):
        artifact = make_artifact(width=200, height=100)
        processed = pad(
            resize(
                crop(artifact, left=20, top=10, width=100, height=50),
                width=200,
                height=100,
            ),
            left=5,
            top=7,
            right=0,
            bottom=0,
        )

        self.assertEqual((70.0, 35.0), processed.geometry.map_point_to_source((105.0, 57.0)))


class ImageOperationTests(unittest.TestCase):
    def test_percentile_normalize_keeps_flat_image_unchanged(self):
        image = np.full((4, 4, 3), 20, dtype=np.uint8)

        np.testing.assert_array_equal(
            image,
            percentile_normalize(image, low=40, high=99),
        )

    def test_enhancement_operations_preserve_uint8_image_contract(self):
        image = np.zeros((16, 16, 3), dtype=np.uint8)
        image[4:12, 4:12] = (10, 20, 30)

        result = top_hat(
            lab_clahe(
                gaussian_blur(gamma_correct(image, gamma=1.2), kernel_size=3),
                clip_limit=2.0,
                tile_grid_size=(8, 8),
            ),
            kernel_size=3,
            strength=1.2,
        )

        self.assertEqual(image.shape, result.shape)
        self.assertEqual(np.uint8, result.dtype)

    def test_channel_and_colour_conversions_have_expected_shapes(self):
        image = np.zeros((8, 8, 3), dtype=np.uint8)
        image[:, :] = (10, 20, 30)

        scaled = scale_bgr_channels(image, blue=2.0, green=1.0, red=0.5)
        self.assertEqual((20, 20, 15), tuple(int(value) for value in scaled[0, 0]))
        self.assertEqual((8, 8), to_gray(image).shape)
        self.assertEqual((8, 8, 3), to_hsv(image).shape)

    def test_canny_edges_returns_single_channel_edge_mask(self):
        image = np.zeros((16, 16, 3), dtype=np.uint8)
        image[4:12, 4:12] = (255, 255, 255)

        edges = canny_edges(image, low=20, high=80)

        self.assertEqual((16, 16), edges.shape)
        self.assertEqual(np.uint8, edges.dtype)
        self.assertGreater(np.count_nonzero(edges), 0)


class MaskOperationTests(unittest.TestCase):
    def test_filter_small_components_discards_only_components_below_threshold(self):
        mask = np.zeros((10, 10), dtype=np.uint8)
        mask[1, 1] = 255
        mask[5:8, 5:8] = 255

        filtered = filter_small_components(mask, min_area=2)

        self.assertEqual(9, np.count_nonzero(filtered))

    def test_masks_support_colour_exclusion_morphology_and_weighted_fusion(self):
        image = np.zeros((16, 16, 3), dtype=np.uint8)
        image[4:12, 4:12] = (0, 0, 255)
        hsv = to_hsv(image)

        red = hsv_range_mask(hsv, lower=(0, 100, 100), upper=(10, 255, 255))
        saturated = saturation_mask(image, threshold=100)
        exclusion = circle_mask((16, 16), center=(8, 8), radius=2)
        combined = weighted_mask_fusion(
            first=morphology(red, operation="close", kernel_shape="rect", kernel_size=3),
            first_weight=1.0,
            second=saturated,
            second_weight=1.0,
        )

        self.assertGreater(np.count_nonzero(combined), 0)
        self.assertGreater(np.count_nonzero(intersect_masks(red, saturated)), 0)
        self.assertEqual(0, np.count_nonzero(subtract_mask(combined, exclusion)[8, 8]))


if __name__ == "__main__":
    unittest.main()
