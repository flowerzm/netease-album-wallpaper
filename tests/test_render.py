from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from netease_album_wallpaper.color import analyze_cover
from netease_album_wallpaper.layout import (
    add_fillers,
    choose_geometry,
    initial_layout,
    optimize_layout,
)
from netease_album_wallpaper.render import render_wallpaper


class RenderSmokeTest(unittest.TestCase):
    def test_synthetic_gallery_renders(self) -> None:
        colors = [
            (10, 10, 10),
            (230, 30, 40),
            (240, 170, 30),
            (30, 180, 80),
            (20, 100, 220),
            (160, 60, 200),
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = []
            for index, color in enumerate(colors):
                path = root / f"{index}.png"
                Image.new("RGB", (128, 128), color).save(path)
                paths.append(path)

            features = [analyze_cover(path) for path in paths]
            geometry = choose_geometry(len(features), 800, 600, gap=6)
            features = add_fillers(features, geometry.slots)
            layout = initial_layout(features, geometry.columns, geometry.rows)
            layout, _, _ = optimize_layout(
                layout,
                features,
                geometry.columns,
                geometry.rows,
                iterations=200,
            )
            output = root / "wallpaper.png"
            render_wallpaper(
                features,
                layout,
                geometry,
                output,
                width=800,
                height=600,
            )
            with Image.open(output) as rendered:
                self.assertEqual(rendered.size, (800, 600))


if __name__ == "__main__":
    unittest.main()

