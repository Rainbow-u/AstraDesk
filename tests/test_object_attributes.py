"""object_attributes 确定性属性单测（Phase 4 阶段 B / B1）。

覆盖：中文色名规则分档（12 色）、颜色提取确定性（同图同框同结果）、
纯色/分区图主色、无原图 → unknown（不编造）、退化框 → unknown、
几何分档（横/方/竖 × 小/中/大）、object_attributes 结构与语义预留 blocked。
"""
from __future__ import annotations

import pytest
from PIL import Image

from packages.understanding.object_attributes import (
    COLOR_NAMES_ZH,
    UNKNOWN_COLOR,
    blocked_semantic,
    color_name_zh,
    extract_color,
    geometry_attrs,
    object_attributes,
    unknown_color,
)


def _solid(color, w=40, h=40) -> Image.Image:
    return Image.new("RGB", (w, h), color)


# ---------------------------------------------------------------- 色名规则

@pytest.mark.parametrize("hsv,expected", [
    ((0.0, 0.0, 0.10), "黑"),      # 低明度
    ((0.0, 0.0, 0.95), "白"),      # 无彩色高明度
    ((0.0, 0.05, 0.50), "灰"),     # 无彩色中明度
    ((0.0, 1.0, 1.0), "红"),       # 正红
    ((350.0, 1.0, 1.0), "红"),     # 红跨 360 边界
    ((30.0, 1.0, 1.0), "橙"),
    ((60.0, 1.0, 1.0), "黄"),
    ((120.0, 1.0, 1.0), "绿"),
    ((180.0, 1.0, 1.0), "青"),
    ((240.0, 1.0, 1.0), "蓝"),
    ((275.0, 1.0, 0.50), "紫"),
    ((30.0, 1.0, 0.40), "棕"),     # 暖色相偏暗
    ((340.0, 0.30, 0.95), "粉"),   # 红/品红偏亮低饱和
])
def test_color_name_zh_bands(hsv, expected):
    assert color_name_zh(*hsv) == expected


def test_color_names_all_reachable():
    """12 个中文基本色名都能被规则命中（无死名）。"""
    hit = {color_name_zh(*hsv) for hsv in [
        (0, 0, 0.1), (0, 0, 0.95), (0, 0.05, 0.5), (0, 1, 1), (30, 1, 1),
        (60, 1, 1), (120, 1, 1), (180, 1, 1), (240, 1, 1), (275, 1, 0.5),
        (30, 1, 0.4), (340, 0.3, 0.95),
    ]}
    assert hit == set(COLOR_NAMES_ZH)


# ---------------------------------------------------------------- 颜色提取

def test_extract_color_solid_red():
    c = extract_color(_solid((255, 0, 0)), [0.0, 0.0, 1.0, 1.0])
    assert c["name"] == "红"
    assert c["rgb"] == [255, 0, 0]
    assert c["hsv"][0] == 0.0 and c["hsv"][1] == 1.0


def test_extract_color_solid_blue_white_black():
    assert extract_color(_solid((0, 0, 255)), [0, 0, 1, 1])["name"] == "蓝"
    assert extract_color(_solid((255, 255, 255)), [0, 0, 1, 1])["name"] == "白"
    assert extract_color(_solid((0, 0, 0)), [0, 0, 1, 1])["name"] == "黑"


def test_extract_color_deterministic():
    """同图同框多次调用结果完全一致（可复现）。"""
    img = _solid((30, 90, 180), w=64, h=48)
    bbox = [0.25, 0.25, 0.75, 0.75]
    assert extract_color(img, bbox) == extract_color(img, bbox)


def test_extract_color_uses_bbox_region_only():
    """左半蓝、右半红：框在左半 → 蓝，框在右半 → 红（证明按框裁剪而非整图）。"""
    img = Image.new("RGB", (80, 40))
    img.paste((0, 0, 255), (0, 0, 40, 40))
    img.paste((255, 0, 0), (40, 0, 80, 40))
    assert extract_color(img, [0.0, 0.0, 0.45, 1.0])["name"] == "蓝"
    assert extract_color(img, [0.55, 0.0, 1.0, 1.0])["name"] == "红"


def test_extract_color_no_image_unknown():
    c = extract_color(None, [0, 0, 1, 1])
    assert c == unknown_color()
    assert c["name"] == UNKNOWN_COLOR and c["rgb"] is None and c["hsv"] is None


def test_extract_color_degenerate_bbox_unknown():
    img = _solid((10, 20, 30))
    assert extract_color(img, [0.5, 0.5, 0.5, 0.5])["name"] == UNKNOWN_COLOR  # 零面积
    assert extract_color(img, None)["name"] == UNKNOWN_COLOR                   # 无框


# ---------------------------------------------------------------- 几何派生

@pytest.mark.parametrize("bbox,orient,size", [
    ([0.0, 0.0, 0.60, 0.20], "landscape", "large"),   # aspect 3.0, area 0.12
    ([0.0, 0.0, 0.10, 0.40], "portrait", "medium"),   # aspect 0.25, area 0.04
    ([0.0, 0.0, 0.20, 0.20], "square", "medium"),     # aspect 1.0, area 0.04
    ([0.0, 0.0, 0.10, 0.10], "square", "small"),      # area 0.01
    ([0.0, 0.0, 0.50, 0.50], "square", "large"),      # area 0.25
])
def test_geometry_attrs_bands(bbox, orient, size):
    g = geometry_attrs(bbox)
    assert g["orientation"] == orient
    assert g["size_class"] == size
    assert g["aspect_ratio"] >= 0.0


def test_geometry_attrs_aspect_ratio_value():
    assert geometry_attrs([0.0, 0.0, 0.40, 0.20])["aspect_ratio"] == 2.0


def test_geometry_attrs_rejects_bad_bbox():
    with pytest.raises(ValueError):
        geometry_attrs([0.0, 0.0, 1.0])


# ---------------------------------------------------------------- 组合 + 语义预留

def test_object_attributes_with_image():
    attrs = object_attributes(_solid((0, 128, 0)), [0, 0, 1, 1], [0.0, 0.0, 0.4, 0.2])
    assert set(attrs) == {"color", "aspect_ratio", "orientation", "size_class", "semantic"}
    assert attrs["color"]["name"] == "绿"
    assert attrs["orientation"] == "landscape"
    # 语义属性恒 blocked（B 阶段预留，VL 凭据未到位）
    assert attrs["semantic"]["status"] == "blocked"
    assert all(attrs["semantic"][k] is None
               for k in ("material", "open_state", "fill_level", "precise_orientation"))


def test_object_attributes_without_image_color_unknown():
    """显式 objects 路径无原图：颜色 unknown，但几何仍确定性可算。"""
    attrs = object_attributes(None, None, [0.0, 0.0, 0.1, 0.4])
    assert attrs["color"]["name"] == UNKNOWN_COLOR
    assert attrs["orientation"] == "portrait"
    assert attrs["semantic"] == blocked_semantic()


def test_object_attributes_deterministic():
    img = _solid((200, 150, 100), w=48, h=48)
    a1 = object_attributes(img, [0.1, 0.1, 0.9, 0.9], [0.1, 0.1, 0.5, 0.3])
    a2 = object_attributes(img, [0.1, 0.1, 0.9, 0.9], [0.1, 0.1, 0.5, 0.3])
    assert a1 == a2
