"""scene_facts 确定性几何计算 + 契约校验（Phase 3）。

覆盖：分区、九宫格、占用/留白、连续工作区、聚类、对齐、取用便利、H07 距离、
非法输入报错、以及“同输入同输出”的确定性（可复现）。
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from PIL import Image

from packages.understanding.scene_facts import (
    PRODUCT_CLASSES,
    SceneFactsError,
    SceneObject,
    compute_scene_facts,
    rect_gap,
    zone_of,
)

CONTRACTS = Path(__file__).resolve().parents[1] / "contracts"


def _validator() -> jsonschema.Draft202012Validator:
    schema = json.loads((CONTRACTS / "scene_facts.schema.json").read_text(encoding="utf-8"))
    return jsonschema.Draft202012Validator(schema)


def _scene():
    return [
        SceneObject("o1", "laptop", [0.30, 0.55, 0.70, 0.90], class_id=0, fixed=True),
        SceneObject("o2", "mouse", [0.74, 0.72, 0.84, 0.82], class_id=3, high_frequency=True),
        SceneObject("o3", "cup", [0.10, 0.60, 0.18, 0.72], class_id=7),
        SceneObject("o4", "book", [0.10, 0.10, 0.26, 0.24], class_id=5),
        SceneObject("o5", "book", [0.28, 0.11, 0.42, 0.25], class_id=5),
        SceneObject("o6", "pen", [0.50, 0.15, 0.54, 0.30], class_id=6),
    ]


def test_output_validates_against_schema():
    facts = compute_scene_facts(_scene(), user_side="bottom", handedness="right", mode="office")
    _validator().validate(facts)  # 不抛即通过
    assert facts["object_count"] == 6
    assert facts["schema_version"]


def test_deterministic_same_input_same_output():
    a = compute_scene_facts(_scene())
    b = compute_scene_facts(_scene())
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_zone_bottom_user_side():
    # 靠用户侧=bottom：y 越大越靠近用户(near)，x 决定 left/center/right
    assert zone_of(0.2, 0.9, "bottom")["depth"] == "near"
    assert zone_of(0.2, 0.9, "bottom")["lateral"] == "left"
    assert zone_of(0.5, 0.5, "bottom")["depth"] == "mid"
    assert zone_of(0.5, 0.5, "bottom")["lateral"] == "center"
    assert zone_of(0.9, 0.1, "bottom")["depth"] == "far"
    assert zone_of(0.9, 0.1, "bottom")["lateral"] == "right"


def test_zone_flips_with_user_side():
    # 同一物理点，用户侧改到 top 时 depth 反转
    assert zone_of(0.5, 0.9, "bottom")["depth"] == "near"
    assert zone_of(0.5, 0.9, "top")["depth"] == "far"


def test_h07_separation_detected():
    near = [
        SceneObject("cup1", "cup", [0.40, 0.40, 0.48, 0.50]),
        SceneObject("lap1", "laptop", [0.50, 0.40, 0.90, 0.80]),  # 与 cup 仅隔 0.02
    ]
    facts = compute_scene_facts(near)
    h07 = facts["h07_separation"]
    assert h07["applicable"] is True
    assert h07["min_distance"] == pytest.approx(0.02, abs=1e-6)
    assert h07["separated"] is False  # 距离 < 0.04 阈值

    far = [
        SceneObject("cup1", "cup", [0.02, 0.02, 0.10, 0.12]),
        SceneObject("lap1", "laptop", [0.60, 0.60, 0.95, 0.95]),
    ]
    h07b = compute_scene_facts(far)["h07_separation"]
    assert h07b["separated"] is True
    assert h07b["min_distance"] > h07b["threshold"]


def test_h07_not_applicable_without_drinkware():
    facts = compute_scene_facts([SceneObject("lap1", "laptop", [0.2, 0.2, 0.6, 0.6])])
    assert facts["h07_separation"]["applicable"] is False
    assert facts["h07_separation"]["min_distance"] is None


def test_continuous_workspace_full_on_empty_desk():
    # 空桌面：工作区应几乎全空
    facts = compute_scene_facts([], grid_n=20)
    assert facts["continuous_workspace"]["largest_empty_rect_ratio"] == pytest.approx(1.0, abs=0.02)
    assert facts["occupancy"]["free_ratio"] == pytest.approx(1.0)


def test_grouping_clusters_same_class():
    facts = compute_scene_facts(_scene())
    clusters = {c["class_name"]: c for c in facts["grouping"]["clusters"]}
    assert clusters["book"]["count"] == 2  # 两本书邻近聚成一簇
    # 功能组：writing 组含 book+pen ≥2 → 有 grouping_score
    writing = next(g for g in facts["grouping"]["functional_groups"] if g["group"] == "writing")
    assert writing["count"] == 3
    assert writing["grouping_score"] is not None


def test_single_instance_group_no_penalty():
    facts = compute_scene_facts([SceneObject("m", "mouse", [0.4, 0.4, 0.5, 0.5])])
    # electronics 组只有 1 个 → grouping_score 为 None（不惩罚）
    elec = next(g for g in facts["grouping"]["functional_groups"] if g["group"] == "electronics")
    assert elec["count"] == 1
    assert elec["grouping_score"] is None
    assert facts["grouping"]["grouping_score"] is None


def test_accessibility_lists_high_frequency():
    facts = compute_scene_facts(_scene(), handedness="right")
    hf = facts["accessibility"]["high_frequency_items"]
    assert [x["object_id"] for x in hf] == ["o2"]
    assert facts["accessibility"]["mouse_side"] == "right"


def test_rect_gap_overlap_zero_and_positive():
    assert rect_gap([0, 0, 1, 1], [0.5, 0.5, 1.5, 1.5]) == 0.0
    assert rect_gap([0, 0, 0.2, 0.2], [0.5, 0, 0.7, 0.2]) == pytest.approx(0.3, abs=1e-6)


@pytest.mark.parametrize("mutate", [
    lambda objs: objs.append(SceneObject("o1", "cup", [0.0, 0.0, 0.1, 0.1])),  # 重复 id
    lambda objs: objs.append(SceneObject("", "cup", [0.0, 0.0, 0.1, 0.1])),     # 空 id
    lambda objs: objs.append(SceneObject("x", "cup", [0.5, 0.5, 0.4, 0.6])),    # x2<x1
    lambda objs: objs.append(SceneObject("x", "cup", [-0.1, 0.0, 0.1, 0.1])),   # 越界
    lambda objs: objs.append(SceneObject("x", "tv", [0.0, 0.0, 0.1, 0.1])),     # 非产品类
])
def test_invalid_inputs_raise(mutate):
    objs = _scene()
    mutate(objs)
    with pytest.raises(SceneFactsError):
        compute_scene_facts(objs)


def test_invalid_user_side_raises():
    with pytest.raises(SceneFactsError):
        compute_scene_facts(_scene(), user_side="upside")


def test_product_classes_matches_category_map():
    """PRODUCT_CLASSES 必须与 configs/category_map.yaml(version 2) 产品词表一致(单一事实来源)。"""
    from packages.vision.category_map import load_category_map, product_names
    assert list(PRODUCT_CLASSES) == product_names(load_category_map())


# ---------------------------------------------------------------- 属性（Phase 4 阶段 B）

def _solid_image(color, w=100, h=100):
    return Image.new("RGB", (w, h), color)


def test_attributes_geometry_always_present():
    """几何属性恒可由 bbox_desk 派生（无需原图）。"""
    facts = compute_scene_facts([SceneObject("c", "cup", [0.10, 0.10, 0.30, 0.50])])
    attrs = facts["objects"][0]["attributes"]
    assert set(attrs) == {"color", "aspect_ratio", "orientation", "size_class", "semantic"}
    # w=0.2 h=0.4 → aspect 0.5 → portrait；area 0.08 → medium
    assert attrs["orientation"] == "portrait"
    assert attrs["size_class"] == "medium"
    assert attrs["aspect_ratio"] == pytest.approx(0.5, abs=1e-6)


def test_attributes_color_unknown_without_image():
    """无原图（显式 objects 路径）→ 颜色 unknown，不编造 rgb/hsv。"""
    facts = compute_scene_facts([SceneObject("c", "cup", [0.1, 0.1, 0.3, 0.3])])
    assert facts["objects"][0]["attributes"]["color"] == {"name": "unknown", "rgb": None, "hsv": None}


def test_attributes_color_from_image():
    """传入原图 + bbox_image → 提取真实主色（确定性）。"""
    img = _solid_image((200, 30, 30))  # 红
    obj = SceneObject("c", "cup", [0.2, 0.2, 0.6, 0.6], bbox_image=[0.2, 0.2, 0.6, 0.6])
    color = compute_scene_facts([obj], image=img)["objects"][0]["attributes"]["color"]
    assert color["name"] == "红"
    assert color["rgb"] is not None and color["hsv"] is not None


def test_attributes_semantic_blocked():
    """语义属性预留块恒 blocked（全 null），待 VL 凭据到位。"""
    facts = compute_scene_facts([SceneObject("c", "cup", [0.1, 0.1, 0.3, 0.3])])
    sem = facts["objects"][0]["attributes"]["semantic"]
    assert sem["status"] == "blocked"
    assert all(sem[k] is None for k in ("material", "open_state", "fill_level", "precise_orientation"))


def test_attributes_deterministic_and_schema_valid():
    """同图同框同结果（可复现），且带属性的事实过契约校验。"""
    img = _solid_image((30, 60, 200))  # 蓝
    objs = [SceneObject("c", "cup", [0.2, 0.2, 0.5, 0.7], bbox_image=[0.2, 0.2, 0.5, 0.7])]
    a = compute_scene_facts(objs, image=img)
    b = compute_scene_facts(objs, image=img)
    assert a["objects"][0]["attributes"] == b["objects"][0]["attributes"]
    _validator().validate(a)  # 不抛即通过


def test_attributes_color_uses_bbox_image_geometry_uses_bbox_desk():
    """坐标不混用（S1 回归）：颜色按 bbox_image 裁剔原图、几何按 bbox_desk 分档。

    构造左红右蓝原图：bbox_image 落在左半（红），bbox_desk 为横放区；
    若两者混用，颜色会错取右半（蓝）或几何会错判为竖放。
    """
    img = Image.new("RGB", (100, 100))
    img.paste((200, 30, 30), (0, 0, 50, 100))    # 左半红
    img.paste((30, 60, 200), (50, 0, 100, 100))  # 右半蓝
    obj = SceneObject("c", "cup", [0.60, 0.10, 0.90, 0.30],  # bbox_desk：w=0.3>h=0.2 → landscape
                      bbox_image=[0.0, 0.0, 0.40, 1.0])       # bbox_image：左半红区
    attrs = compute_scene_facts([obj], image=img)["objects"][0]["attributes"]
    assert attrs["color"]["name"] == "红"          # 取自 bbox_image 左半，非 bbox_desk 对应区
    assert attrs["orientation"] == "landscape"    # 取自 bbox_desk 宽高比
