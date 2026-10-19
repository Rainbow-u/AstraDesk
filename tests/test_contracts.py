"""契约样例校验（G1）：合法样例通过、非法样例被拒。"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
from referencing import Registry, Resource

CONTRACTS = Path(__file__).resolve().parents[1] / "contracts"


def _load(name: str) -> dict:
    return json.loads((CONTRACTS / name).read_text(encoding="utf-8"))


def _registry() -> Registry:
    schemas = [_load("detection_result.schema.json"), _load("error.schema.json")]
    return Registry().with_resources(
        [(s["$id"], Resource.from_contents(s)) for s in schemas]
    )


def _validator(schema_name: str) -> jsonschema.Draft202012Validator:
    schema = _load(schema_name)
    return jsonschema.Draft202012Validator(schema, registry=_registry())


def test_detection_result_valid_passes():
    v = _validator("detection_result.schema.json")
    sample = _load("samples/detection_result.valid.json")
    v.validate(sample)  # 不抛异常即通过


def test_detection_result_invalid_rejected():
    v = _validator("detection_result.schema.json")
    sample = _load("samples/detection_result.invalid.json")
    errors = list(v.iter_errors(sample))
    assert errors, "非法样例本应被拒绝"
    # 至少覆盖：status 非法枚举、confidence>1、bbox_image 长度错误
    joined = " ".join(e.message for e in errors)
    assert "done" in joined or "status" in joined.lower()


def test_detection_class_enum_enforced():
    """新枚举(version 2)：class_id 超出 0-23 或 class_name 非产品类词表均被拒。"""
    v = _validator("detection_result.schema.json")
    base = _load("samples/detection_result.valid.json")

    bad_id = json.loads(json.dumps(base))
    bad_id["detections"][0]["class_id"] = 63  # COCO 旧 id，不属产品类
    assert list(v.iter_errors(bad_id)), "class_id=63 本应被新枚举拒绝"

    bad_name = json.loads(json.dumps(base))
    bad_name["detections"][0]["class_name"] = "tv"  # 非 23 产品类+other
    assert list(v.iter_errors(bad_name)), "class_name=tv 本应被新枚举拒绝"

    other = json.loads(json.dumps(base))
    other["detections"][0]["class_id"] = 23
    other["detections"][0]["class_name"] = "other"  # 兼底类合法(version 2 索引=23)
    v.validate(other)


def test_scene_facts_valid_passes():
    v = _validator("scene_facts.schema.json")
    v.validate(_load("samples/scene_facts.valid.json"))


def test_scene_facts_invalid_rejected():
    v = _validator("scene_facts.schema.json")
    errors = list(v.iter_errors(_load("samples/scene_facts.invalid.json")))
    assert errors, "非法 scene_facts 样例本应被拒绝"
    joined = " ".join(e.message for e in errors)
    # 至少覆盖：user_side 非法枚举 / class_name=tv / 缺失必需字段
    assert "upside" in joined or "tv" in joined or "density" in joined


def _mutate_first_attrs(v, mutate):
    """复制合法样例、对首个 object 的 attributes 施加 mutate，返回是否被 schema 拒绝。"""
    sample = json.loads(json.dumps(_load("samples/scene_facts.valid.json")))
    mutate(sample["objects"][0]["attributes"])
    return list(v.iter_errors(sample))


def test_scene_facts_attributes_valid_structure():
    """合法样例每个 object.attributes 结构完整（颜色/几何/语义预留块）。"""
    sample = _load("samples/scene_facts.valid.json")
    for obj in sample["objects"]:
        attrs = obj["attributes"]
        assert set(attrs) == {"color", "aspect_ratio", "orientation", "size_class", "semantic"}
        assert set(attrs["color"]) == {"name", "rgb", "hsv"}
        assert attrs["semantic"]["status"] == "blocked"


def test_scene_facts_attributes_invalid_rejected():
    """Phase4-B3：attributes 各处非法均被 schema 拒绝（受控 additionalProperties:false）。"""
    v = _validator("scene_facts.schema.json")

    # 1) orientation 坏枚举
    assert _mutate_first_attrs(v, lambda a: a.update({"orientation": "diagonal"}))
    # 2) color.name 非 12 基本色+unknown
    assert _mutate_first_attrs(v, lambda a: a["color"].update({"name": "turquoise"}))
    # 3) size_class 坏枚举
    assert _mutate_first_attrs(v, lambda a: a.update({"size_class": "huge"}))
    # 4) semantic 加受控外字段（VL 不得越权扩展）
    assert _mutate_first_attrs(v, lambda a: a["semantic"].update({"weight": 1.2}))
    # 5) attributes 整体缺失（必填）
    assert _mutate_first_attrs(v, lambda a: a.clear())
    # 6) aspect_ratio 负数
    assert _mutate_first_attrs(v, lambda a: a.update({"aspect_ratio": -0.5}))


def test_scene_facts_attributes_color_unknown_valid():
    """颜色 unknown（无原图）合法：rgb/hsv 为 null，不得编造数值。"""
    v = _validator("scene_facts.schema.json")
    sample = json.loads(json.dumps(_load("samples/scene_facts.valid.json")))
    sample["objects"][0]["attributes"]["color"] = {"name": "unknown", "rgb": None, "hsv": None}
    v.validate(sample)  # 不抛即通过


def test_vl_relations_valid_passes():
    v = _validator("vl_relations.schema.json")
    v.validate(_load("samples/vl_relations.valid.json"))


def test_vl_relations_invalid_rejected():
    """W3/H01：非法 vl_relations 样例被拒——未知谓词 on_top_of、空 subject_id、
    缺必需 explanation、额外顶层属性 rewritten_facts（VL 不得改写事实清单）。"""
    v = _validator("vl_relations.schema.json")
    errors = list(v.iter_errors(_load("samples/vl_relations.invalid.json")))
    assert errors, "非法 vl_relations 样例本应被拒绝"
    joined = " ".join(e.message for e in errors)
    assert ("on_top_of" in joined or "explanation" in joined
            or "rewritten_facts" in joined or "subject_id" in joined)


def test_error_valid_passes():
    v = _validator("error.schema.json")
    v.validate(_load("samples/error.valid.json"))


def test_error_invalid_rejected():
    v = _validator("error.schema.json")
    errors = list(v.iter_errors(_load("samples/error.invalid.json")))
    assert errors, "非法错误样例本应被拒绝（未知 code / request_id 缺失 / retryable 类型错误）"
