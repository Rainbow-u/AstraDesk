"""坐标契约转换（PRD 5.2 / AGENTS.md 约定3）。

- ``bbox_image = [x1, y1, x2, y2]``：相对整张原图归一化 0-1，左上原点，x 向右、y 向下。
- ``desk_bbox_image = [dx1, dy1, dx2, dy2]``：桌面矩形，使用同一原图坐标。
- ``bbox_desk``：相对桌面矩形归一化；``x_desk = (x_image - dx1) / (dx2 - dx1)``，y 同理。

``bbox_desk`` 一律由后端从原图框与桌面范围推导，客户端传值需经校验（不得两模块各自计算后并存）。
``desk_to_image(image_to_desk(b, d), d) == b`` 必须有往返测试覆盖。
"""
from __future__ import annotations

from typing import List, Sequence

Bbox = List[float]


class CoordinateError(ValueError):
    """坐标非法（桌面矩形退化、bbox 长度错误、越界等）。"""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _check_bbox(bbox: Sequence[float], name: str) -> tuple:
    if len(bbox) != 4:
        raise CoordinateError("SCHEMA_INVALID", f"{name} must have 4 floats, got {len(bbox)}")
    x1, y1, x2, y2 = (float(v) for v in bbox)
    if x2 < x1 or y2 < y1:
        raise CoordinateError("SCHEMA_INVALID", f"{name} has x2<x1 or y2<y1: {bbox}")
    return x1, y1, x2, y2


def _desk_wh(desk_bbox_image: Sequence[float]) -> tuple:
    dx1, dy1, dx2, dy2 = _check_bbox(desk_bbox_image, "desk_bbox_image")
    dw = dx2 - dx1
    dh = dy2 - dy1
    if dw <= 0 or dh <= 0:
        raise CoordinateError("SCHEMA_INVALID", f"desk_bbox_image degenerate (w={dw}, h={dh})")
    return dx1, dy1, dw, dh


def image_to_desk(bbox_image: Sequence[float], desk_bbox_image: Sequence[float]) -> Bbox:
    """原图归一化框 → 桌面归一化框。结果可能超出 [0,1]（物体部分在桌面外），不裁剪。"""
    x1, y1, x2, y2 = _check_bbox(bbox_image, "bbox_image")
    dx1, dy1, dw, dh = _desk_wh(desk_bbox_image)
    return [(x1 - dx1) / dw, (y1 - dy1) / dh, (x2 - dx1) / dw, (y2 - dy1) / dh]


def desk_to_image(bbox_desk: Sequence[float], desk_bbox_image: Sequence[float]) -> Bbox:
    """桌面归一化框 → 原图归一化框（``image_to_desk`` 的逆运算）。"""
    x1, y1, x2, y2 = _check_bbox(bbox_desk, "bbox_desk")
    dx1, dy1, dw, dh = _desk_wh(desk_bbox_image)
    return [x1 * dw + dx1, y1 * dh + dy1, x2 * dw + dx1, y2 * dh + dy1]


def clamp01(bbox: Sequence[float]) -> Bbox:
    """把归一化框裁剪到 [0,1]，用于展示与越界检查辅助。"""
    x1, y1, x2, y2 = (float(v) for v in bbox)
    return [min(max(x1, 0.0), 1.0), min(max(y1, 0.0), 1.0),
            min(max(x2, 0.0), 1.0), min(max(y2, 0.0), 1.0)]
