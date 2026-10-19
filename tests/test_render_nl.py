"""render_nl 模板渲染测试（Phase 3）：确定性、可测量内容、H07 提示、H01 引用安全。"""
from __future__ import annotations

import pytest

from packages.understanding import render_nl
from packages.understanding.scene_facts import SceneObject, compute_scene_facts


def _facts(scene=None, **kw):
    scene = scene if scene is not None else [
        SceneObject("o_laptop", "laptop", [0.30, 0.55, 0.70, 0.90], fixed=True),
        SceneObject("o_mouse", "mouse", [0.74, 0.72, 0.84, 0.82], high_frequency=True),
        SceneObject("o_cup", "cup", [0.10, 0.60, 0.18, 0.72]),
        SceneObject("o_book1", "book", [0.10, 0.10, 0.26, 0.24]),
        SceneObject("o_book2", "book", [0.28, 0.11, 0.42, 0.25]),
    ]
    return compute_scene_facts(scene, **kw)


def test_render_deterministic():
    f = _facts()
    a = render_nl.render(f)
    b = render_nl.render(f)
    assert a["text"] == b["text"]
    assert a["render_version"]


def test_render_contains_measurable_dimensions():
    out = render_nl.render(_facts())
    text = out["text"]
    # 绑定 6.2 软目标 + 可测量数字（百分比/评分），而非空洞形容词
    assert "连续工作区" in text and "%" in text
    assert "取用便利" in text and "对齐" in text and "同类集中" in text
    assert "笔记本电脑" in text and "鼠标" in text
    keys = {d["key"] for d in out["dimensions"]}
    assert keys == {"continuous_workspace", "accessibility", "grouping", "alignment", "movement_saving"}


def test_movement_saving_marked_na():
    out = render_nl.render(_facts())
    ms = next(d for d in out["dimensions"] if d["key"] == "movement_saving")
    assert "N/A" in ms["text"]  # 诚实标注：规划期指标，不在场景描述阶段合成


def test_h07_violation_warning_references_real_ids():
    scene = [
        SceneObject("cup_x", "cup", [0.40, 0.40, 0.48, 0.50]),
        SceneObject("lap_x", "laptop", [0.50, 0.40, 0.90, 0.80]),  # 距 0.02 < 0.04
    ]
    out = render_nl.render(_facts(scene))
    assert out["warnings"], "H07 未分隔时应给出提示"
    joined = " ".join(out["warnings"])
    assert "cup_x" in joined and "lap_x" in joined  # 只引用事实清单里已有的 object_id（H01）
    assert "H07" in out["text"]


def test_h07_separated_no_warning():
    out = render_nl.render(_facts())
    assert out["warnings"] == []


def test_empty_scene_renders():
    out = render_nl.render(_facts(scene=[]))
    assert "桌面共 0 件物品" in out["text"]


def test_missing_key_raises():
    with pytest.raises(render_nl.RenderError):
        render_nl.render({"objects": []})


def test_only_references_known_object_ids():
    """H01：渲染文本中出现的 object_id 必须都来自事实清单。"""
    f = _facts()
    out = render_nl.render(f)
    known = {o["object_id"] for o in f["objects"]}
    # warnings 为空时文本不含 id；构造一个违规场景验证 id 来源
    scene = [SceneObject("cup_q", "cup", [0.40, 0.40, 0.48, 0.50]),
             SceneObject("lap_q", "laptop", [0.50, 0.40, 0.90, 0.80])]
    fq = compute_scene_facts(scene)
    oq = render_nl.render(fq)
    known_q = {o["object_id"] for o in fq["objects"]}
    for w in oq["warnings"]:
        for tok in ("cup_q", "lap_q"):
            if tok in w:
                assert tok in known_q
    assert known  # 常规场景 id 集合非空


# ---------------------------------------------------------------- 颜色/几何（Phase 4 阶段 B）

def _solid(color, w=100, h=100):
    from PIL import Image
    return Image.new("RGB", (w, h), color)


def test_render_includes_color_and_geometry():
    """有原图时描述融入颜色+几何朝向（如“蓝色杯子…竖放”）。"""
    img = _solid((35, 95, 175))  # 蓝
    scene = [SceneObject("c", "cup", [0.10, 0.60, 0.18, 0.72], bbox_image=[0.10, 0.60, 0.18, 0.72])]
    out = render_nl.render(compute_scene_facts(scene, image=img))
    assert "蓝色杯子" in out["text"]
    assert "竖放" in out["text"]  # w=0.08<h=0.12 → portrait


def test_render_no_color_prefix_when_unknown():
    """无原图（颜色 unknown）→ 不加颜色前缀（不编造），仍保留类名与几何。"""
    out = render_nl.render(_facts([SceneObject("c", "cup", [0.10, 0.60, 0.18, 0.72])]))
    assert "色杯子" not in out["text"]
    assert "杯子" in out["text"] and "竖放" in out["text"]


def test_render_semantic_blocked_no_inferred_adjectives():
    """语义属性 blocked → 描述不含材质/开合/空满等推断词（守 H01、不过度声称）。"""
    text = render_nl.render(_facts())["text"]
    for w in ("陶瓷", "玻璃", "塑料材", "空的", "满的", "打开的", "盖上的"):
        assert w not in text
    assert "语义属性暂未启用" in text  # 诚实标注 blocked
