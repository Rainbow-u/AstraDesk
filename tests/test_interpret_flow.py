"""interpret 任务端到端测试（Phase 3）：确定性 facts + 模板 NL，经完整 API 栈。

覆盖：显式 objects 与 detect_job_id 两种物品来源、结果内 scene_facts 过契约校验、
描述文本非空、VL 增强如实标注 blocked、非法请求报错、跨项目引用被拒。
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from packages.understanding.scene_facts import PRODUCT_CLASSES

CONTRACTS = Path(__file__).resolve().parents[1] / "contracts"


def _facts_validator() -> jsonschema.Draft202012Validator:
    schema = json.loads((CONTRACTS / "scene_facts.schema.json").read_text(encoding="utf-8"))
    return jsonschema.Draft202012Validator(schema)


def _wait_job(client, job_id: str, tries: int = 30) -> dict:
    job = {}
    for _ in range(tries):
        job = client.get(f"/api/v1/jobs/{job_id}").json()
        if job["status"] in ("succeeded", "failed", "cancelled"):
            return job
    return job


def _post_interpret(client, project_id, payload):
    return client.post(f"/api/v1/projects/{project_id}/jobs/interpret", json=payload)


def test_capabilities_advertise_interpret(client):
    caps = client.get("/api/v1/capabilities").json()
    assert "interpret" in caps["features"]


def test_interpret_from_explicit_objects(client):
    proj = client.post("/api/v1/projects", json={"title": "理解"}).json()
    payload = {
        "desk_bbox_image": [0.0, 0.0, 1.0, 1.0],
        "user_side": "bottom", "handedness": "right", "mode": "office",
        "objects": [
            {"object_id": "a", "class_name": "laptop", "bbox_image": [0.30, 0.55, 0.70, 0.90], "fixed": True},
            {"object_id": "b", "class_name": "mouse", "bbox_image": [0.74, 0.72, 0.84, 0.82], "high_frequency": True},
            {"object_id": "c", "class_name": "cup", "bbox_image": [0.10, 0.60, 0.18, 0.72]},
        ],
    }
    created = _post_interpret(client, proj["id"], payload)
    assert created.status_code == 202, created.text
    job = _wait_job(client, created.json()["id"])
    assert job["status"] == "succeeded", job
    assert job["type"] == "interpret"
    result = job["result"]
    assert result["count"] == 3
    _facts_validator().validate(result["scene_facts"])  # 内嵌事实过契约
    assert result["description"]["text"].strip()
    assert result["vl"]["enabled"] is False  # VL 增强如实标注 blocked
    # W-new-2：回写事实推导基准（约定3 可追溯）——显式提供了桌面框
    assert result["desk_bbox_image"] == [0.0, 0.0, 1.0, 1.0]
    assert result["desk_assumed_full_image"] is False
    # 事实里的类别都属于产品词表
    for o in result["scene_facts"]["objects"]:
        assert o["class_name"] in PRODUCT_CLASSES


def test_interpret_from_detect_job(client, sample_png):
    proj = client.post("/api/v1/projects", json={"title": "检测转理解"}).json()
    up = client.post(f"/api/v1/projects/{proj['id']}/images",
                     files={"file": ("desk.png", sample_png, "image/png")})
    det = client.post(f"/api/v1/projects/{proj['id']}/jobs/detect",
                      json={"image_asset_id": up.json()["image_asset_id"]})
    det_job = _wait_job(client, det.json()["id"])
    assert det_job["status"] == "succeeded"

    created = _post_interpret(client, proj["id"], {"detect_job_id": det_job["id"]})
    assert created.status_code == 202, created.text
    job = _wait_job(client, created.json()["id"])
    assert job["status"] == "succeeded", job
    assert job["result"]["count"] == len(det_job["detections"])  # mock 检测 2 件
    # W-new-2：未传桌面框 → 回写“全图当桌面”假设标记（约定3 可追溯）
    assert job["result"]["desk_assumed_full_image"] is True
    assert job["result"]["desk_bbox_image"] == [0.0, 0.0, 1.0, 1.0]


def test_interpret_explicit_objects_color_unknown(client):
    """Phase4-B2：显式 objects 路径无关联原图 → 颜色 unknown（不编造），几何仍派生。"""
    proj = client.post("/api/v1/projects", json={"title": "无图属性"}).json()
    payload = {
        "desk_bbox_image": [0.0, 0.0, 1.0, 1.0],
        "objects": [
            {"object_id": "c", "class_name": "cup", "bbox_image": [0.10, 0.60, 0.18, 0.72]},
        ],
    }
    created = _post_interpret(client, proj["id"], payload)
    job = _wait_job(client, created.json()["id"])
    assert job["status"] == "succeeded", job
    attrs = job["result"]["scene_facts"]["objects"][0]["attributes"]
    assert attrs["color"] == {"name": "unknown", "rgb": None, "hsv": None}
    assert attrs["orientation"] in ("landscape", "square", "portrait")  # 几何无需原图
    assert attrs["semantic"]["status"] == "blocked"


def test_interpret_detect_job_extracts_color(client, sample_png):
    """Phase4-B2：detect_job 路径关联原图 → 从像素提取真实主色（非 unknown）。"""
    proj = client.post("/api/v1/projects", json={"title": "检测取色"}).json()
    up = client.post(f"/api/v1/projects/{proj['id']}/images",
                     files={"file": ("desk.png", sample_png, "image/png")})
    det = client.post(f"/api/v1/projects/{proj['id']}/jobs/detect",
                      json={"image_asset_id": up.json()["image_asset_id"]})
    det_job = _wait_job(client, det.json()["id"])
    created = _post_interpret(client, proj["id"], {"detect_job_id": det_job["id"]})
    job = _wait_job(client, created.json()["id"])
    assert job["status"] == "succeeded", job
    for o in job["result"]["scene_facts"]["objects"]:
        color = o["attributes"]["color"]
        assert color["name"] != "unknown", color
        assert color["rgb"] is not None and color["hsv"] is not None
        assert o["attributes"]["semantic"]["status"] == "blocked"


def test_interpret_requires_source(client):
    proj = client.post("/api/v1/projects", json={}).json()
    resp = _post_interpret(client, proj["id"], {"user_side": "bottom"})
    assert resp.status_code == 400
    assert resp.json()["code"] == "INVALID_REQUEST"


def test_interpret_rejects_cross_project_detect_job(client, sample_png):
    p1 = client.post("/api/v1/projects", json={"title": "A"}).json()
    p2 = client.post("/api/v1/projects", json={"title": "B"}).json()
    up = client.post(f"/api/v1/projects/{p1['id']}/images",
                     files={"file": ("desk.png", sample_png, "image/png")})
    det = client.post(f"/api/v1/projects/{p1['id']}/jobs/detect",
                      json={"image_asset_id": up.json()["image_asset_id"]})
    det_job = _wait_job(client, det.json()["id"])
    # 用 p2 引用 p1 的检测任务 → 404
    resp = _post_interpret(client, p2["id"], {"detect_job_id": det_job["id"]})
    assert resp.status_code == 404
    assert resp.json()["code"] == "JOB_NOT_FOUND"


def test_interpret_invalid_class_fails_job(client):
    proj = client.post("/api/v1/projects", json={}).json()
    payload = {"objects": [{"object_id": "x", "class_name": "tv", "bbox_image": [0.1, 0.1, 0.3, 0.3]}]}
    created = _post_interpret(client, proj["id"], payload)
    job = _wait_job(client, created.json()["id"])
    assert job["status"] == "failed"
    assert job["error"]["code"] == "SCHEMA_INVALID"
