"""融合(类无关 NMS、主检测优先)与开放词表→产品类映射单测。"""
import pytest

from packages.vision.detector import Detection
from packages.vision.fusion import fuse, iou
from packages.vision.open_vocab import OTHER_ID, OTHER_NAME, openvocab_to_product


def _det(cid, name, box, conf=0.5, source="yolov10:yolov10_desk_fine"):
    return Detection(class_id=cid, class_name=name, confidence=conf, bbox_image=list(box), source=source)


def test_iou_bounds():
    assert iou([0, 0, 1, 1], [0, 0, 1, 1]) == 1.0
    assert iou([0, 0, 0.5, 0.5], [0.6, 0.6, 1, 1]) == 0.0
    assert 0.0 < iou([0, 0, 0.6, 0.6], [0.4, 0.4, 1, 1]) < 1.0


def test_primary_kept_and_source_preserved():
    primary = [_det(0, "laptop", [0.1, 0.1, 0.5, 0.5])]
    out = fuse(primary, [])
    assert len(out) == 1
    assert out[0].source == "yolov10:yolov10_desk_fine"
    assert out[0].class_name == "laptop"
    assert out[0].raw_class_name == ""  # 主检测无开放词表原始名


def test_overlapping_secondary_suppressed():
    primary = [_det(0, "laptop", [0.1, 0.1, 0.5, 0.5])]
    secondary = [_det(0, "laptop", [0.12, 0.12, 0.52, 0.52], conf=0.9, source="yolo-world")]
    out = fuse(primary, secondary, iou_thr=0.5)
    assert len(out) == 1  # 重叠→信任主检测，抑制补检测
    assert out[0].source == "yolov10:yolov10_desk_fine"


def test_nonoverlapping_secondary_kept_and_mapped():
    primary = [_det(0, "laptop", [0.1, 0.1, 0.4, 0.4])]
    secondary = [_det(5, "pen", [0.7, 0.7, 0.9, 0.9], conf=0.4, source="yolo-world")]
    out = fuse(primary, secondary, iou_thr=0.5)
    assert len(out) == 2
    added = [d for d in out if d.source == "yolo-world"][0]
    assert added.class_name == "pen"
    assert added.class_id == 6  # version 2: pen 索引=6（由 mapper 覆写，非开放词表原始 cid）
    assert added.raw_class_name == "pen"  # 原始提示词名保留


def test_extra_prompt_maps_to_other():
    # tablet 属候选池(本轮未转正)，映射为 other；headphones/cable/lamp/tissue 已在 version 2 转正
    primary = []
    secondary = [_det(15, "tablet", [0.2, 0.2, 0.4, 0.4], conf=0.5, source="yolo-world")]
    out = fuse(primary, secondary)
    assert out[0].class_name == OTHER_NAME
    assert out[0].class_id == OTHER_ID
    assert out[0].raw_class_name == "tablet"  # 映射为 other 后仍保留原始名(FR03)


def test_secondary_to_other_preserves_raw_class_name():
    """W-new-3/W8：speaker 等非产品类提示词映射为 other 后，raw_class_name 保留原始名。"""
    out = fuse([], [_det(9, "speaker", [0.3, 0.3, 0.5, 0.5], conf=0.4, source="yolo-world")])
    assert out[0].class_id == OTHER_ID and out[0].class_name == OTHER_NAME
    assert out[0].raw_class_name == "speaker"


def test_secondary_self_dedup():
    secondary = [
        _det(5, "pen", [0.2, 0.2, 0.4, 0.4], conf=0.6, source="yolo-world"),
        _det(5, "pen", [0.21, 0.21, 0.41, 0.41], conf=0.3, source="yolo-world"),
    ]
    out = fuse([], secondary, iou_thr=0.5)
    assert len(out) == 1  # 两个高重叠补检测只留置信度高的


@pytest.mark.parametrize("name,expected", [
    # version 2 产品类(含杯瓶细分与转正类)映射到自身
    ("laptop", "laptop"), ("mobile phone", "mobile_phone"), ("cup", "cup"),
    ("thermos cup", "thermos_cup"), ("plastic bottle", "plastic_bottle"),
    ("can", "can"), ("waterpot", "waterpot"), ("mouse pad", "mouse_pad"),
    ("headphones", "headphones"), ("cable", "cable"), ("lamp", "lamp"), ("tissue", "tissue"),
    # 候选池/非产品类 -> other
    ("document", OTHER_NAME), ("speaker", OTHER_NAME), ("tablet", OTHER_NAME),
    ("earphones", OTHER_NAME),
])
def test_openvocab_mapping(name, expected):
    assert openvocab_to_product(name)[1] == expected
