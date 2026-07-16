from __future__ import annotations

import json
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from .color import CoverFeature, analyze_cover
from .layout import (
    Geometry,
    add_fillers,
    choose_geometry,
    initial_layout,
    optimize_layout,
    separate_fillers,
)
from .netease import DownloadResult, NeteaseError, download_albums, fetch_playlist_albums
from .render import render_wallpaper, write_layout_csv


@dataclass(frozen=True)
class GenerationResult:
    wallpaper: Path
    layout_csv: Path
    manifest_json: Path
    geometry: Geometry
    album_count: int
    filler_count: int
    failed_downloads: int
    energy_improvement: float


def _write_manifest(
    path: Path,
    playlist,
    downloads: list[DownloadResult],
    geometry: Geometry,
    result: GenerationResult,
) -> None:
    payload = {
        "playlist": asdict(playlist),
        "summary": {
            "unique_albums": result.album_count,
            "failed_downloads": result.failed_downloads,
            "fillers": result.filler_count,
            "energy_improvement_percent": round(result.energy_improvement * 100, 2),
        },
        "geometry": asdict(geometry),
        "albums": [download.to_dict() for download in downloads],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def generate_wallpaper(
    playlist_input: str,
    output: Path,
    covers_dir: Path | None = None,
    width: int = 3840,
    height: int = 2400,
    gap: int = 10,
    radius: int | None = None,
    background: str = "#090c13",
    workers: int = 4,
    retries: int = 2,
    iterations: int | None = None,
    shadow: bool = True,
    progress=None,
) -> GenerationResult:
    if width < 640 or height < 480:
        raise ValueError("画布尺寸至少为 640×480")
    if gap < 0 or gap > 100:
        raise ValueError("间距必须在 0 到 100 之间")
    if output.suffix.lower() != ".png":
        output = output.with_suffix(".png")

    playlist, albums = fetch_playlist_albums(playlist_input, progress)
    temporary: tempfile.TemporaryDirectory[str] | None = None
    if covers_dir is None:
        temporary = tempfile.TemporaryDirectory(prefix="netease-album-wallpaper-")
        active_covers_dir = Path(temporary.name)
    else:
        active_covers_dir = covers_dir

    try:
        downloads = download_albums(
            albums,
            active_covers_dir,
            workers=workers,
            retries=retries,
            progress=progress,
        )
        successful = [download for download in downloads if download.path is not None]
        if not successful:
            raise NeteaseError("没有成功下载任何专辑封面")

        features: list[CoverFeature] = []
        for index, download in enumerate(successful, 1):
            assert download.path is not None
            features.append(analyze_cover(download.path))
            if progress and index % 40 == 0:
                progress(f"分析封面色彩：{index}/{len(successful)}")

        geometry = choose_geometry(len(features), width, height, gap)
        original_count = len(features)
        features = add_fillers(features, geometry.slots)
        layout = initial_layout(features, geometry.columns, geometry.rows)
        layout, energy_before, energy_after = optimize_layout(
            layout,
            features,
            geometry.columns,
            geometry.rows,
            iterations=iterations,
            progress=progress,
        )
        separate_fillers(layout, features, geometry.columns, geometry.rows)
        improvement = 1.0 - energy_after / energy_before if energy_before else 0.0
        if progress:
            progress(
                f"网格：{geometry.columns}×{geometry.rows}；封面 {geometry.tile_size}px；"
                f"补位 {geometry.slots - original_count} 张"
            )
            progress(f"相邻色差改善：{improvement * 100:.1f}%")

        render_wallpaper(
            features,
            layout,
            geometry,
            output,
            width=width,
            height=height,
            radius=radius,
            background=background,
            shadow=shadow,
            progress=progress,
        )
        layout_csv = output.with_suffix(".layout.csv")
        manifest_json = output.with_suffix(".manifest.json")
        write_layout_csv(layout_csv, features, layout, geometry)
        result = GenerationResult(
            wallpaper=output,
            layout_csv=layout_csv,
            manifest_json=manifest_json,
            geometry=geometry,
            album_count=original_count,
            filler_count=geometry.slots - original_count,
            failed_downloads=len(downloads) - len(successful),
            energy_improvement=improvement,
        )
        _write_manifest(manifest_json, playlist, downloads, geometry, result)
        return result
    finally:
        if temporary is not None:
            temporary.cleanup()

