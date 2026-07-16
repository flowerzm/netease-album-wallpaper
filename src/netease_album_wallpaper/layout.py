from __future__ import annotations

import math
import random
from dataclasses import dataclass

import numpy as np

from .color import CoverFeature


@dataclass(frozen=True)
class Geometry:
    columns: int
    rows: int
    tile_size: int
    gap: int
    origin_x: int
    origin_y: int

    @property
    def slots(self) -> int:
        return self.columns * self.rows


def choose_geometry(
    count: int,
    width: int,
    height: int,
    gap: int = 10,
    minimum_margin_ratio: float = 0.04,
) -> Geometry:
    if count < 1:
        raise ValueError("至少需要一张封面")
    target_ratio = width / height
    candidates: list[tuple[float, int, int]] = []
    for rows in range(2, max(4, int(math.sqrt(count) * 2.2)) + 1):
        columns = math.ceil(count / rows)
        if columns < rows:
            continue
        duplicates = columns * rows - count
        ratio_error = abs(math.log((columns / rows) / target_ratio))
        score = ratio_error * 30.0 + duplicates * 0.60
        candidates.append((score, columns, rows))
    if not candidates:
        raise ValueError("无法为封面数量选择网格")
    _, columns, rows = min(candidates)

    margin_x = round(width * minimum_margin_ratio)
    margin_y = round(height * minimum_margin_ratio)
    max_tile_width = (width - 2 * margin_x - (columns - 1) * gap) // columns
    max_tile_height = (height - 2 * margin_y - (rows - 1) * gap) // rows
    tile_size = int(min(max_tile_width, max_tile_height))
    tile_size = max(32, (tile_size // 10) * 10)

    content_width = columns * tile_size + (columns - 1) * gap
    content_height = rows * tile_size + (rows - 1) * gap
    return Geometry(
        columns=columns,
        rows=rows,
        tile_size=tile_size,
        gap=gap,
        origin_x=(width - content_width) // 2,
        origin_y=(height - content_height) // 2,
    )


def add_fillers(features: list[CoverFeature], slots: int) -> list[CoverFeature]:
    if len(features) > slots:
        raise ValueError("封面数量超过网格容量")
    result = list(features)
    if len(result) == slots:
        return result

    labs = np.stack([feature.lab for feature in features])
    distances = np.sum((labs[:, None, :] - labs[None, :, :]) ** 2, axis=2)
    neighbor_count = min(7, len(features))
    density = np.sort(distances, axis=1)[:, 1:neighbor_count].mean(axis=1)
    candidates = np.argsort(density)
    for fill_index in range(slots - len(result)):
        source_index = int(candidates[fill_index % len(candidates)])
        source = features[source_index]
        result.append(
            CoverFeature(
                path=source.path,
                lab=source.lab.copy(),
                hue=source.hue,
                chroma=source.chroma,
                lightness=source.lightness,
                duplicate_of=source_index,
            )
        )
    return result


def initial_layout(features: list[CoverFeature], columns: int, rows: int) -> list[int]:
    neutral_threshold = 13.0

    def horizontal_key(index: int) -> tuple[float, float, float]:
        feature = features[index]
        if feature.chroma < neutral_threshold:
            return (-1.0, feature.lightness, feature.chroma)
        return (feature.hue / 360.0, feature.lightness, feature.chroma)

    ordered = sorted(range(len(features)), key=horizontal_key)
    layout = [-1] * (columns * rows)
    for column in range(columns):
        group = ordered[column * rows : (column + 1) * rows]
        group.sort(key=lambda index: (features[index].lightness, features[index].chroma))
        for row, index in enumerate(group):
            layout[row * columns + column] = index
    if any(index < 0 for index in layout):
        raise ValueError("网格未被完全填充")
    return layout


def _neighbors(position: int, columns: int, rows: int) -> tuple[int, ...]:
    row, column = divmod(position, columns)
    result: list[int] = []
    if column > 0:
        result.append(position - 1)
    if column + 1 < columns:
        result.append(position + 1)
    if row > 0:
        result.append(position - columns)
    if row + 1 < rows:
        result.append(position + columns)
    return tuple(result)


def total_energy(
    layout: list[int], labs: np.ndarray, columns: int, rows: int
) -> float:
    total = 0.0
    for position, image_index in enumerate(layout):
        row, column = divmod(position, columns)
        if column + 1 < columns:
            delta = labs[image_index] - labs[layout[position + 1]]
            total += float(delta @ delta)
        if row + 1 < rows:
            delta = labs[image_index] - labs[layout[position + columns]]
            total += float(delta @ delta)
    return total


def optimize_layout(
    layout: list[int],
    features: list[CoverFeature],
    columns: int,
    rows: int,
    iterations: int | None = None,
    seed: int = 20260717,
    progress=None,
) -> tuple[list[int], float, float]:
    iterations = iterations or max(60000, len(layout) * 700)
    labs = np.stack([feature.lab for feature in features])
    adjacency = [_neighbors(position, columns, rows) for position in range(len(layout))]
    rng = random.Random(seed)
    before_total = total_energy(layout, labs, columns, rows)

    def edges_for(first: int, second: int) -> set[tuple[int, int]]:
        edges: set[tuple[int, int]] = set()
        for position in (first, second):
            for other in adjacency[position]:
                edges.add((min(position, other), max(position, other)))
        return edges

    def local_energy(edges: set[tuple[int, int]]) -> float:
        total = 0.0
        for left, right in edges:
            delta = labs[layout[left]] - labs[layout[right]]
            total += float(delta @ delta)
        return total

    count = len(layout)
    for iteration in range(iterations):
        first = rng.randrange(count)
        row, column = divmod(first, columns)
        if rng.random() < 0.88:
            other_column = min(columns - 1, max(0, column + rng.randint(-4, 4)))
            other_row = min(rows - 1, max(0, row + rng.randint(-3, 3)))
            second = other_row * columns + other_column
        else:
            second = rng.randrange(count)
        if first == second:
            continue

        edges = edges_for(first, second)
        before = local_energy(edges)
        layout[first], layout[second] = layout[second], layout[first]
        after = local_energy(edges)
        if after >= before:
            layout[first], layout[second] = layout[second], layout[first]
        if progress and iteration and iteration % 50000 == 0:
            progress(f"色彩邻接优化：{iteration}/{iterations}")

    after_total = total_energy(layout, labs, columns, rows)
    return layout, before_total, after_total


def separate_fillers(
    layout: list[int], features: list[CoverFeature], columns: int, rows: int
) -> None:
    labs = np.stack([feature.lab for feature in features])
    for duplicate_index, feature in enumerate(features):
        if feature.duplicate_of is None:
            continue
        duplicate_position = layout.index(duplicate_index)
        source_position = layout.index(feature.duplicate_of)
        distance = abs(duplicate_position // columns - source_position // columns) + abs(
            duplicate_position % columns - source_position % columns
        )
        if distance >= 5:
            continue
        candidates: list[tuple[float, int]] = []
        for position, image_index in enumerate(layout):
            source_distance = abs(position // columns - source_position // columns) + abs(
                position % columns - source_position % columns
            )
            if source_distance < 7:
                continue
            color_distance = float(np.sum((labs[image_index] - feature.lab) ** 2))
            candidates.append((color_distance, position))
        if candidates:
            _, swap_position = min(candidates)
            layout[duplicate_position], layout[swap_position] = (
                layout[swap_position],
                layout[duplicate_position],
            )

