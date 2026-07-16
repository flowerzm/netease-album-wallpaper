from __future__ import annotations

import unittest

import numpy as np

from netease_album_wallpaper.color import rgb_to_lab
from netease_album_wallpaper.layout import choose_geometry


class ColorTests(unittest.TestCase):
    def test_black_and_white_lightness(self) -> None:
        labs = rgb_to_lab(np.array([[0, 0, 0], [255, 255, 255]]))
        self.assertAlmostEqual(float(labs[0, 0]), 0.0, places=4)
        self.assertAlmostEqual(float(labs[1, 0]), 100.0, places=3)


class GeometryTests(unittest.TestCase):
    def test_285_covers_use_22_by_13(self) -> None:
        geometry = choose_geometry(285, 3840, 2400, 10)
        self.assertEqual((geometry.columns, geometry.rows), (22, 13))
        self.assertEqual(geometry.slots, 286)

    def test_156_covers_use_16_by_10(self) -> None:
        geometry = choose_geometry(156, 3840, 2400, 10)
        self.assertEqual((geometry.columns, geometry.rows), (16, 10))
        self.assertEqual(geometry.slots, 160)


if __name__ == "__main__":
    unittest.main()

