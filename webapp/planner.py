from __future__ import annotations

import math
from dataclasses import asdict, dataclass


@dataclass
class Piece:
    pid: int
    x: float
    y: float
    w: float
    h: float
    kind: str

    def to_dict(self):
        return asdict(self)


def _segments(cell_count: int, max_cells: int) -> list[int]:
    count = math.ceil(cell_count / max_cells)
    base, remainder = divmod(cell_count, count)
    return [base + (1 if index < remainder else 0) for index in range(count)]


def _pack(lengths: list[float], maximum: float) -> list[float]:
    packed: list[float] = []
    current = 0.0
    for length in lengths:
        if current and current + length > maximum + 1e-7:
            packed.append(current)
            current = 0.0
        if length > maximum + 1e-7:
            raise ValueError("边缘尺寸超过打印机范围，请减小边缘格数或增大打印尺寸")
        current += length
    if current:
        packed.append(current)
    return packed


def _kind(x: float, y: float, w: float, h: float, width: float, depth: float) -> str:
    left, right = abs(x) < 1e-7, abs(x + w - width) < 1e-7
    bottom, top = abs(y) < 1e-7, abs(y + h - depth) < 1e-7
    if left and top:
        return "corner_lt"
    if right and top:
        return "corner_rt"
    if left and bottom:
        return "corner_lb"
    if right and bottom:
        return "corner_rb"
    if left:
        return "edge_left"
    if right:
        return "edge_right"
    if top:
        return "edge_top"
    if bottom:
        return "edge_bottom"
    return "center"


def make_plan(width: float, depth: float, printer_x: float, printer_y: float,
              grid: float = 42.0, min_margin_cells: int = 1) -> dict:
    values = (width, depth, printer_x, printer_y, grid)
    if any(not math.isfinite(value) or value <= 0 for value in values):
        raise ValueError("所有尺寸都必须是大于 0 的数字")
    if min_margin_cells < 0 or min_margin_cells > 10:
        raise ValueError("边缘格数需要在 0 到 10 之间")
    if printer_x < grid or printer_y < grid:
        raise ValueError("打印尺寸不能小于一个网格")

    min_margin = min_margin_cells * grid
    if width < grid + 2 * min_margin or depth < grid + 2 * min_margin:
        raise ValueError("抽屉太小，无法同时容纳当前网格和对称边缘")

    gx = math.floor((width - 2 * min_margin) / grid)
    gy = math.floor((depth - 2 * min_margin) / grid)
    margin_x = (width - gx * grid) / 2
    margin_y = (depth - gy * grid) / 2
    if margin_x > printer_x + 1e-7 or margin_y > printer_y + 1e-7:
        raise ValueError("对称边缘超过打印机范围，请减小边缘格数或增大打印尺寸")

    x_center = _segments(gx, max(1, math.floor(printer_x / grid)))
    y_center = _segments(gy, max(1, math.floor(printer_y / grid)))
    center_widths = [cells * grid for cells in x_center]
    center_heights = [cells * grid for cells in y_center]

    x_atomic = [margin_x] + [grid] * gx + [margin_x]
    y_atomic = [margin_y] + [grid] * gy + [margin_y]
    edge_x = _pack(x_atomic, printer_x)
    edge_y = _pack(y_atomic, printer_y)

    pieces: list[Piece] = []

    def add(x: float, y: float, w: float, h: float):
        if w <= 1e-7 or h <= 1e-7:
            return
        pieces.append(Piece(len(pieces) + 1, x, y, w, h, _kind(x, y, w, h, width, depth)))

    x = 0.0
    for segment in edge_x:
        add(x, 0.0, segment, margin_y)
        add(x, depth - margin_y, segment, margin_y)
        x += segment

    y = margin_y
    for segment in center_heights:
        add(0.0, y, margin_x, segment)
        add(width - margin_x, y, margin_x, segment)
        y += segment

    y = margin_y
    for segment_h in center_heights:
        x = margin_x
        for segment_w in center_widths:
            add(x, y, segment_w, segment_h)
            x += segment_w
        y += segment_h

    pieces.sort(key=lambda piece: (piece.y, piece.x))
    for pid, piece in enumerate(pieces, 1):
        piece.pid = pid

    return {
        "drawer": {"width": width, "depth": depth},
        "printer": {"width": printer_x, "depth": printer_y},
        "grid": grid,
        "grid_count": {"x": gx, "y": gy, "total": gx * gy},
        "margins": {"left": margin_x, "right": margin_x, "top": margin_y, "bottom": margin_y},
        "piece_count": len(pieces),
        "pieces": [piece.to_dict() for piece in pieces],
    }


def fit_for_kind(kind: str) -> tuple[int, int]:
    mapping = {
        "corner_lt": (-1, 1), "corner_rt": (1, 1),
        "corner_lb": (-1, -1), "corner_rb": (1, -1),
        "edge_top": (0, 1), "edge_bottom": (0, -1),
        "edge_left": (-1, 0), "edge_right": (1, 0),
        "center": (0, 0),
    }
    return mapping[kind]
