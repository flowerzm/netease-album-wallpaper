from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps


@dataclass
class CoverFeature:
    path: Path
    lab: np.ndarray
    hue: float
    chroma: float
    lightness: float
    duplicate_of: int | None = None


def rgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    """Convert one or more sRGB triples (0..255) to CIE L*a*b* (D65)."""
    values = np.asarray(rgb, dtype=np.float64) / 255.0
    linear = np.where(
        values <= 0.04045,
        values / 12.92,
        ((values + 0.055) / 1.055) ** 2.4,
    )
    matrix = np.array(
        [
            [0.4124564, 0.3575761, 0.1804375],
            [0.2126729, 0.7151522, 0.0721750],
            [0.0193339, 0.1191920, 0.9503041],
        ]
    )
    xyz = (linear @ matrix.T) / np.array([0.95047, 1.0, 1.08883])
    delta = 6 / 29
    f = np.where(
        xyz > delta**3,
        np.cbrt(xyz),
        xyz / (3 * delta**2) + 4 / 29,
    )
    return np.stack(
        [
            116 * f[..., 1] - 16,
            500 * (f[..., 0] - f[..., 1]),
            200 * (f[..., 1] - f[..., 2]),
        ],
        axis=-1,
    )


def analyze_cover(path: Path) -> CoverFeature:
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
        thumb = ImageOps.fit(image, (96, 96), method=Image.Resampling.LANCZOS)

    quantized = thumb.quantize(colors=7, method=Image.Quantize.MEDIANCUT)
    palette = quantized.getpalette()
    colors = sorted(quantized.getcolors(maxcolors=256) or [], reverse=True)
    if not colors or palette is None:
        raise ValueError(f"无法提取封面主色：{path}")

    counts = np.array([count for count, _ in colors], dtype=np.float64)
    rgbs = np.array(
        [palette[index * 3 : index * 3 + 3] for _, index in colors],
        dtype=np.float64,
    )
    labs = rgb_to_lab(rgbs)
    weights = counts / counts.sum()
    dominant = labs[0]
    weighted_mean = np.sum(labs * weights[:, None], axis=0)
    lab = dominant * 0.62 + weighted_mean * 0.38
    chroma = float(np.hypot(lab[1], lab[2]))
    hue = float((math.degrees(math.atan2(lab[2], lab[1])) + 360.0) % 360.0)
    return CoverFeature(
        path=path,
        lab=lab,
        hue=hue,
        chroma=chroma,
        lightness=float(lab[0]),
    )

