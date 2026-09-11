from __future__ import annotations

import unittest

from core.actions import StickSlewLimiter


class StickSlewLimiterTests(unittest.TestCase):
    def test_moves_towards_target_by_a_bounded_distance(self):
        limiter = StickSlewLimiter(max_delta_per_second=100_000)

        self.assertEqual((0, 0), limiter.update(30_000, 0, elapsed_ms=0))
        self.assertEqual((5_000, 0), limiter.update(30_000, 0, elapsed_ms=50))
        self.assertEqual((10_000, 0), limiter.update(30_000, 0, elapsed_ms=50))

    def test_reaches_target_without_overshoot_and_resets_to_neutral(self):
        limiter = StickSlewLimiter(max_delta_per_second=100_000)

        self.assertEqual((30_000, -12_000), limiter.update(30_000, -12_000, elapsed_ms=500))
        self.assertEqual((0, 0), limiter.reset())
        self.assertEqual((0, 0), limiter.current)

    def test_rejects_invalid_elapsed_time_and_axis_values(self):
        limiter = StickSlewLimiter()

        with self.assertRaises(ValueError):
            limiter.update(0, 0, elapsed_ms=-1)
        with self.assertRaises(ValueError):
            limiter.update(32_768, 0, elapsed_ms=10)


if __name__ == "__main__":
    unittest.main()
