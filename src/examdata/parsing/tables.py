"""表格结构还原。

Cambridge Mark Scheme 与部分试卷使用规整的表格版式。纯按文本流顺序解析
会丢失"哪一格属于哪一列"的信息，因此用矢量线条还原行列边界。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import pymupdf

from .pdfdoc import PageInfo


@dataclass
class TableGrid:
    """一页上的表格网格。"""

    page: int
    column_edges: list[float] = field(default_factory=list)
    row_edges: list[float] = field(default_factory=list)

    @property
    def column_ranges(self) -> list[tuple[float, float]]:
        return list(zip(self.column_edges, self.column_edges[1:]))

    @property
    def row_ranges(self) -> list[tuple[float, float]]:
        return list(zip(self.row_edges, self.row_edges[1:]))

    def column_of(self, x: float) -> Optional[int]:
        for i, (a, b) in enumerate(self.column_ranges):
            if a <= x < b:
                return i
        if self.column_ranges and x >= self.column_ranges[-1][1]:
            return len(self.column_ranges) - 1
        return None

    def row_of(self, y: float) -> Optional[int]:
        for i, (a, b) in enumerate(self.row_ranges):
            if a <= y < b:
                return i
        return None


def _cluster(values: list[float], tolerance: float = 3.0) -> list[float]:
    """把相近的坐标聚成一个边界值。"""
    if not values:
        return []
    vals = sorted(values)
    groups: list[list[float]] = [[vals[0]]]
    for v in vals[1:]:
        if v - groups[-1][-1] <= tolerance:
            groups[-1].append(v)
        else:
            groups.append([v])
    return [sum(g) / len(g) for g in groups]


def detect_grid(page: Any, page_info: PageInfo, *, min_length: float = 15.0) -> TableGrid:
    """从矢量线条还原行列边界。"""
    verticals: list[float] = []
    horizontals: list[float] = []

    try:
        drawings = page.get_drawings()
    except Exception:
        drawings = []

    for d in drawings:
        for item in d.get("items", []):
            kind = item[0]
            if kind == "l":
                p1, p2 = item[1], item[2]
                if abs(p1.x - p2.x) <= 1.5 and abs(p1.y - p2.y) >= min_length:
                    verticals.append((p1.x + p2.x) / 2)
                elif abs(p1.y - p2.y) <= 1.5 and abs(p1.x - p2.x) >= min_length:
                    horizontals.append((p1.y + p2.y) / 2)
            elif kind == "re":
                r = item[1]
                if r.width <= 2.0 and r.height >= min_length:
                    verticals.append((r.x0 + r.x1) / 2)
                elif r.height <= 2.0 and r.width >= min_length:
                    horizontals.append((r.y0 + r.y1) / 2)

    # 页面左右边界兜底
    if verticals:
        verticals = [page_info.width * 0.0 + min(verticals), *verticals, max(verticals)]
    grid = TableGrid(
        page=page_info.number,
        column_edges=_cluster(verticals),
        row_edges=_cluster(horizontals),
    )
    return grid


@dataclass
class TableCell:
    column: int
    row: int
    text: str
    bbox: tuple[float, float, float, float]


def fill_cells(page_info: PageInfo, grid: TableGrid) -> list[list[TableCell]]:
    """把文本行填入网格，返回 [row][column] 的单元格矩阵。"""
    if not grid.column_ranges or not grid.row_ranges:
        return []

    matrix: list[list[TableCell]] = [
        [TableCell(column=c, row=r, text="", bbox=(0, 0, 0, 0))
         for c in range(len(grid.column_ranges))]
        for r in range(len(grid.row_ranges))
    ]

    for line in page_info.lines:
        x_center = (line.bbox[0] + line.bbox[2]) / 2
        y_center = (line.bbox[1] + line.bbox[3]) / 2
        col = grid.column_of(x_center)
        row = grid.row_of(y_center)
        if col is None or row is None:
            continue
        cell = matrix[row][col]
        cell.text = (cell.text + "\n" + line.text).strip() if cell.text else line.text
        if cell.bbox == (0, 0, 0, 0):
            cell.bbox = tuple(line.bbox)  # type: ignore[assignment]
        else:
            x0, y0, x1, y1 = cell.bbox
            cell.bbox = (min(x0, line.bbox[0]), min(y0, line.bbox[1]),
                         max(x1, line.bbox[2]), max(y1, line.bbox[3]))

    return matrix


def table_rows_as_text(matrix: list[list[TableCell]]) -> list[list[str]]:
    return [[c.text for c in row] for row in matrix]
