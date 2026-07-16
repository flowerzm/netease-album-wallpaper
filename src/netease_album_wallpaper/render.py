from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from .color import CoverFeature
from .layout import Geometry


def parse_hex_color(value: str) -> tuple[int, int, int]:
    clean = value.strip().lstrip("#")
    if len(clean) == 3:
        clean = "".join(char * 2 for char in clean)
    if len(clean) != 6:
        raise ValueError(f"无效的十六进制颜色：{value}")
    try:
        return tuple(int(clean[index : index + 2], 16) for index in (0, 2, 4))  # type: ignore[return-value]
    except ValueError as exc:
        raise ValueError(f"无效的十六进制颜色：{value}") from exc


def dark_background(
    width: int, height: int, base_color: tuple[int, int, int]
) -> Image.Image:
    y = np.linspace(-1.0, 1.0, height, dtype=np.float32)
    glow = (1.0 - np.abs(y))[:, None]
    base = np.array(base_color, dtype=np.float32)
    lift = np.array([3.0, 4.0, 6.0], dtype=np.float32)
    rows = np.clip(base[None, None, :] + glow[:, :, None] * lift, 0, 255)
    array = np.repeat(rows, width, axis=1).astype(np.uint8)
    return Image.fromarray(array, mode="RGB")


def render_wallpaper(
    features: list[CoverFeature],
    layout: list[int],
    geometry: Geometry,
    output: Path,
    width: int = 3840,
    height: int = 2400,
    radius: int | None = None,
    background: str = "#090c13",
    shadow: bool = True,
    progress=None,
) -> None:
    radius = radius if radius is not None else max(6, round(geometry.tile_size * 0.08))
    canvas = dark_background(width, height, parse_hex_color(background))

    if shadow:
        shadow_mask = Image.new("L", canvas.size, 0)
        draw = ImageDraw.Draw(shadow_mask)
        for position in range(len(layout)):
            row, column = divmod(position, geometry.columns)
            x = geometry.origin_x + column * (geometry.tile_size + geometry.gap)
            y = geometry.origin_y + row * (geometry.tile_size + geometry.gap)
            draw.rounded_rectangle(
                (
                    x,
                    y + 3,
                    x + geometry.tile_size - 1,
                    y + geometry.tile_size + 2,
                ),
                radius=radius,
                fill=105,
            )
        shadow_mask = shadow_mask.filter(ImageFilter.GaussianBlur(4))
        canvas.paste((0, 0, 0), (0, 0, width, height), shadow_mask)

    tile_mask = Image.new("L", (geometry.tile_size, geometry.tile_size), 0)
    ImageDraw.Draw(tile_mask).rounded_rectangle(
        (0, 0, geometry.tile_size - 1, geometry.tile_size - 1),
        radius=radius,
        fill=255,
    )

    for position, feature_index in enumerate(layout):
        row, column = divmod(position, geometry.columns)
        x = geometry.origin_x + column * (geometry.tile_size + geometry.gap)
        y = geometry.origin_y + row * (geometry.tile_size + geometry.gap)
        with Image.open(features[feature_index].path) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            tile = ImageOps.fit(
                image,
                (geometry.tile_size, geometry.tile_size),
                method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.5),
            )
        canvas.paste(tile, (x, y), tile_mask)
        if progress and (position + 1) % 50 == 0:
            progress(f"渲染圆角封面：{position + 1}/{len(layout)}")

    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, "PNG", optimize=True)


def write_layout_csv(
    path: Path,
    features: list[CoverFeature],
    layout: list[int],
    geometry: Geometry,
) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "row",
                "column",
                "file",
                "L",
                "a",
                "b",
                "chroma",
                "hue",
                "filler",
            ],
        )
        writer.writeheader()
        for position, feature_index in enumerate(layout):
            feature = features[feature_index]
            row, column = divmod(position, geometry.columns)
            writer.writerow(
                {
                    "row": row + 1,
                    "column": column + 1,
                    "file": feature.path.name,
                    "L": f"{feature.lab[0]:.3f}",
                    "a": f"{feature.lab[1]:.3f}",
                    "b": f"{feature.lab[2]:.3f}",
                    "chroma": f"{feature.chroma:.3f}",
                    "hue": f"{feature.hue:.3f}",
                    "filler": feature.duplicate_of is not None,
                }
            )

