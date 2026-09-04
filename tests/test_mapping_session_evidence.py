import unittest

import numpy as np

from gui.modes.mapping.runtime.session import MappingSession


class _ScreenCapture:
    def __init__(self, image):
        self.image = image

    def capture_square(self, center_x, center_y, size):
        return self.image


class _Recognizer:
    def __init__(self, match_mask, wall_mask, fog_mask, raw_gray):
        self.match_mask = match_mask
        self.wall_mask = wall_mask
        self.fog_mask = fog_mask
        self.raw_gray = raw_gray

    def extract_combined(self, image, *, player_pos):
        return self.match_mask, self.wall_mask, self.fog_mask

    def get_raw_gray(self, image):
        return self.raw_gray

    def get_preprocessed_image(self, image):
        return image


class _Stitcher:
    def __init__(self):
        self.evidence = None

    def add_evidence(self, evidence):
        self.evidence = evidence


class MappingSessionEvidenceTests(unittest.TestCase):
    def test_tick_passes_current_capture_and_masks_as_typed_evidence(self):
        image = np.zeros((12, 16, 3), dtype=np.uint8)
        match_mask = np.full((12, 16), 1, dtype=np.uint8)
        wall_mask = np.full((12, 16), 2, dtype=np.uint8)
        fog_mask = np.full((12, 16), 3, dtype=np.uint8)
        raw_gray = np.full((12, 16), 4, dtype=np.uint8)
        stitcher = _Stitcher()
        context = type(
            "Context",
            (),
            {
                "monitor_logical_center": True,
                "monitor_size": 16,
                "screen_capture": _ScreenCapture(image),
                "recognizer": _Recognizer(match_mask, wall_mask, fog_mask, raw_gray),
                "stitcher": stitcher,
            },
        )()
        session = MappingSession(
            context,
            get_monitor_center=lambda: (100, 200),
            get_last_player_local_pos=lambda: None,
        )

        result = session.tick()

        self.assertEqual((8, 8), stitcher.evidence.player_position)
        self.assertIs(image, stitcher.evidence.image)
        self.assertIs(match_mask, stitcher.evidence.match_mask)
        self.assertIs(wall_mask, stitcher.evidence.save_mask)
        self.assertIs(fog_mask, stitcher.evidence.fog_mask)
        self.assertIs(raw_gray, stitcher.evidence.raw_gray)
        self.assertEqual((16, 12), result.capture_size)


if __name__ == "__main__":
    unittest.main()
