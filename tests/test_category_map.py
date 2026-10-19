"""类别映射与标签归一化单测（configs/category_map.yaml 为单一事实来源）。"""
import pytest

from packages.vision.category_map import (
    CategoryMapError,
    dataset_to_product,
    load_category_map,
    normalize_class_id,
    product_names,
)


@pytest.fixture(scope="module")
def cmap():
    return load_category_map()


@pytest.mark.parametrize("token,expected", [("8", 8), ("8.0", 8), (8, 8), (8.0, 8), ("0", 0), ("0.0", 0)])
def test_normalize_class_id_int_float_mix(token, expected):
    assert normalize_class_id(token) == expected


def test_product_classes_are_24(cmap):
    """version 2：23 训练类(0-22) + other(23) 兜底，共 24 项。"""
    assert cmap["version"] == 2
    assert len(cmap["product_classes"]) == 24
    assert product_names(cmap) == [
        "laptop", "monitor", "keyboard", "mouse", "mobile_phone", "book", "pen",
        "cup", "thermos_cup", "plastic_cup", "disposable_cup",
        "bottle", "plastic_bottle", "squeeze_bottle", "can", "waterpot",
        "cable", "charger", "tissue", "paper", "lamp", "headphones", "mouse_pad",
        "other",
    ]


@pytest.mark.parametrize("cid,pidx", [
    # 保留类
    (8, 0), (11, 1), (10, 2), (9, 3), (14, 4), (18, 5), (0, 6),
    # 杯细分
    (20, 7), (21, 8), (22, 9), (34, 10),
    # 瓶罐细分
    (72, 11), (32, 12), (79, 13), (33, 14), (55, 15),
    # other 高频物转正
    (17, 16), (16, 17), (42, 18), (39, 19), (56, 20), (12, 21), (27, 22),
])
def test_mapped_dataset_classes(cmap, cid, pidx):
    assert dataset_to_product(cmap, cid) == pidx


@pytest.mark.parametrize("cid", [
    7,    # computer=台式机机箱，目视判定不并入 monitor
    19,   # document 散页文档(样本<150)，候选池归 other
    61,   # pencil case 候选池
    67,   # phone holder 候选池
    15,   # tablet 候选池
    13,   # earphones 候选池
    5,    # 0 样本死类
    62,   # 0 样本死类
])
def test_unmapped_classes_return_none(cmap, cid):
    """未命中映射的一律归 other(不参训)，返回 None。注：paper(39)/mouse pad(27) 已在 version 2 转正，不再属此列。"""
    assert dataset_to_product(cmap, cid) is None


def test_map_targets_are_declared_classes(cmap):
    for cid, pidx in cmap["dataset_to_product"].items():
        assert pidx in cmap["product_classes"]


def test_bad_map_raises(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "version: 1\nproduct_classes:\n  0: laptop\ndataset_to_product:\n  8: 9\n",
        encoding="utf-8",
    )
    with pytest.raises(CategoryMapError):
        load_category_map(bad)
