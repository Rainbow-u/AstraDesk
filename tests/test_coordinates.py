"""坐标契约往返与边界测试（AGENTS.md 约定3；PRD 5.2）。"""
from __future__ import annotations

import pytest

from packages.layout.coordinates import (
    CoordinateError,
    clamp01,
    desk_to_image,
    image_to_desk,
)


def test_roundtrip_full_desk():
    desk = [0.0, 0.0, 1.0, 1.0]
    bbox = [0.12, 0.3, 0.55, 0.78]
    assert image_to_desk(bbox, desk) == pytest.approx(bbox)
    assert desk_to_image(image_to_desk(bbox, desk), desk) == pytest.approx(bbox)


def test_roundtrip_sub_desk():
    desk = [0.1, 0.1, 0.9, 0.9]
    bbox = [0.18, 0.26, 0.34, 0.5]
    d = image_to_desk(bbox, desk)
    # 手工核对 PRD 公式：x_desk=(x_image-dx1)/(dx2-dx1)
    assert d[0] == pytest.approx((0.18 - 0.1) / 0.8)
    assert d[2] == pytest.approx((0.34 - 0.1) / 0.8)
    assert desk_to_image(d, desk) == pytest.approx(bbox)


@pytest.mark.parametrize("bbox,desk", [
    ([0.1, 0.1, 0.5], [0.0, 0.0, 1.0, 1.0]),      # 长度不足
    ([0.5, 0.5, 0.1, 0.9], [0.0, 0.0, 1.0, 1.0]),  # x2<x1
    ([0.1, 0.1, 0.5, 0.5], [0.5, 0.0, 0.5, 1.0]),  # 桌面宽度退化
])
def test_invalid_raises_schema_invalid(bbox, desk):
    with pytest.raises(CoordinateError) as ei:
        image_to_desk(bbox, desk)
    assert ei.value.code == "SCHEMA_INVALID"


def test_object_outside_desk_not_clamped_by_conversion():
    desk = [0.2, 0.2, 0.8, 0.8]
    bbox = [0.1, 0.1, 0.5, 0.5]  # 左上角在桌面外
    d = image_to_desk(bbox, desk)
    assert d[0] < 0 and d[1] < 0  # 转换保留负值，越界检查交由上层
    assert clamp01(d)[0] == 0.0
