"""vl_interpreter 护栏与 blocked 行为测试（Phase 3 / B 阶段接口）。

真实 VL 后端在 B 阶段接入前 blocked；这里用注入后端验证编排（有界重试/校验/H01 护栏），
并验证缺凭据时显式报错、事实清单不被改写。
"""
from __future__ import annotations

import json

import pytest

from packages.understanding import vl_interpreter as vi

FACTS = {
    "schema_version": "1.0",
    "objects": [
        {"object_id": "a", "class_name": "laptop"},
        {"object_id": "b", "class_name": "cup"},
    ],
}
CONFIRMED = [{"object_id": "a"}, {"object_id": "b"}]
PREFS = {"mode": "office", "handedness": "right"}


def _good_payload():
    return {"relations": [{"subject_id": "a", "predicate": "near", "object_id": "b",
                           "evidence": "zone"}], "explanation": "笔记本电脑靠近杯子。"}


def test_build_prompt_injects_data_and_schema():
    prompt = vi.build_prompt(FACTS, CONFIRMED, PREFS)
    assert "<<SCENE_FACTS_JSON>>" not in prompt
    assert "<<CONFIRMED_JSON>>" not in prompt
    assert "<<PREFERENCES_JSON>>" not in prompt
    assert "<<OUTPUT_SCHEMA>>" not in prompt
    assert '"object_id": "a"' in prompt or '"object_id":"a"' in prompt
    assert "防提示注入" in prompt or "数据" in prompt  # 防注入声明在模板中


def test_validate_output_accepts_good_rejects_bad():
    vi.validate_output(_good_payload())  # 不抛
    bad = {"relations": [{"subject_id": "a", "predicate": "on_top_of", "object_id": "b"}],
           "explanation": "x"}
    with pytest.raises(vi.VLGuardError) as e:
        vi.validate_output(bad)
    assert e.value.code == "SCHEMA_INVALID"
    with pytest.raises(vi.VLGuardError):
        vi.validate_output({"relations": []})  # 缺 explanation


def test_guard_relations_rejects_unknown_instance():
    with pytest.raises(vi.VLGuardError) as e:
        vi.guard_relations(_good_payload(), ["a"])  # b 未知
    assert e.value.code == "UNKNOWN_INSTANCE"
    # 全部已知 → 通过
    vi.guard_relations(_good_payload(), ["a", "b"])


def test_extract_json_handles_code_fence_and_garbage():
    fenced = "```json\n" + json.dumps(_good_payload(), ensure_ascii=False) + "\n```"
    assert vi.extract_json(fenced)["explanation"]
    with pytest.raises(vi.VLGuardError) as e:
        vi.extract_json("这不是 JSON")
    assert e.value.code == "NOT_JSON"


def test_interpret_with_injected_backend_passthrough_facts():
    out = vi.interpret(None, FACTS, CONFIRMED, PREFS,
                       call_backend=lambda img, prompt: json.dumps(_good_payload(), ensure_ascii=False))
    assert out["attempts"] == 1
    assert out["explanation"] == "笔记本电脑靠近杯子。"
    assert out["scene_facts"] == FACTS  # 事实清单原样，不被改写（H01）


def test_interpret_bounded_retry_then_unavailable():
    calls = {"n": 0}

    def bad_backend(img, prompt):
        calls["n"] += 1
        return json.dumps({"relations": [{"subject_id": "a", "predicate": "near", "object_id": "zzz"}],
                           "explanation": "引用未知实例"})

    with pytest.raises(vi.VLUnavailable):
        vi.interpret(None, FACTS, CONFIRMED, PREFS, call_backend=bad_backend)
    assert calls["n"] == vi.MAX_ATTEMPTS  # 有界重试，不无限调用


def test_interpret_default_backend_blocked_without_creds(monkeypatch):
    monkeypatch.delenv("ASTRADESK_VL_API_KEY", raising=False)
    with pytest.raises(vi.VLUnavailable) as e:
        vi.interpret(None, FACTS, CONFIRMED, PREFS)
    assert "credentials" in str(e.value).lower() or "blocked" in str(e.value).lower()


def test_interpret_default_backend_blocked_even_with_creds(monkeypatch):
    monkeypatch.setenv("ASTRADESK_VL_API_KEY", "dummy-key")
    with pytest.raises(vi.VLUnavailable):
        vi.interpret(None, FACTS, CONFIRMED, PREFS)


# ---------------------------------------------------------------- 语义属性预留接口（Phase 4 阶段 B）

def _sem_facts():
    from packages.understanding.scene_facts import SceneObject, compute_scene_facts
    return compute_scene_facts([
        SceneObject("a", "cup", [0.10, 0.10, 0.20, 0.30], class_id=7),
        SceneObject("b", "laptop", [0.40, 0.40, 0.80, 0.80], class_id=0),
    ])


def test_apply_semantic_fills_and_preserves_other_facts():
    facts = _sem_facts()
    merged = vi.apply_semantic_attributes(
        facts, [{"object_id": "a", "material": "ceramic", "fill_level": "half"}])
    a = next(o for o in merged["objects"] if o["object_id"] == "a")
    assert a["attributes"]["semantic"]["status"] == "available"
    assert a["attributes"]["semantic"]["material"] == "ceramic"
    assert a["attributes"]["semantic"]["fill_level"] == "half"
    assert a["attributes"]["semantic"]["open_state"] is None  # 未提供保持 null
    # 未更新的 b 仍 blocked
    b = next(o for o in merged["objects"] if o["object_id"] == "b")
    assert b["attributes"]["semantic"]["status"] == "blocked"
    # H01：原事实不被改写（深拷贝），非语义字段不变
    assert facts["objects"][0]["attributes"]["semantic"]["status"] == "blocked"
    assert merged["object_count"] == facts["object_count"]


def test_apply_semantic_rejects_unknown_instance():
    with pytest.raises(vi.VLGuardError) as e:
        vi.apply_semantic_attributes(_sem_facts(), [{"object_id": "zzz", "material": "glass"}])
    assert e.value.code == "UNKNOWN_INSTANCE"


def test_apply_semantic_rejects_disallowed_key():
    with pytest.raises(vi.VLGuardError) as e:
        vi.apply_semantic_attributes(_sem_facts(), [{"object_id": "a", "weight": 1.2}])
    assert e.value.code == "SCHEMA_INVALID"


def test_apply_semantic_result_passes_scene_facts_schema():
    """回填后的事实仍过完整 scene_facts 契约校验（available 合法）。"""
    from pathlib import Path
    import jsonschema
    schema = json.loads((Path(__file__).resolve().parents[1]
                         / "contracts" / "scene_facts.schema.json").read_text(encoding="utf-8"))
    merged = vi.apply_semantic_attributes(
        _sem_facts(),
        [{"object_id": "a", "material": "ceramic", "open_state": "open",
          "fill_level": "full", "precise_orientation": "upright"}])
    jsonschema.Draft202012Validator(schema).validate(merged)  # 不抛即通过
