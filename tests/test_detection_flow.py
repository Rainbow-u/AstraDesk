"""桌面识别端到端流程测试（T02）。

mock 模式跑通：创建项目 → 上传 → 检测任务 → 查询结果；并验证：
- 响应符合 detection_result 契约（G1）；
- 同一任务多次查询 detection id 守恒（H01 的接口层体现）；
- 非法/伪装图像被拒（FR01）；
- real 模式权重缺失时报 MODEL_UNAVAILABLE，不静默回退 mock（约定1）。
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
from referencing import Registry, Resource

CONTRACTS = Path(__file__).resolve().parents[1] / "contracts"


def _validator() -> jsonschema.Draft202012Validator:
    det = json.loads((CONTRACTS / "detection_result.schema.json").read_text(encoding="utf-8"))
    err = json.loads((CONTRACTS / "error.schema.json").read_text(encoding="utf-8"))
    registry = Registry().with_resources(
        [(s["$id"], Resource.from_contents(s)) for s in (det, err)]
    )
    return jsonschema.Draft202012Validator(det, registry=registry)


def _upload(client, png):
    proj = client.post("/api/v1/projects", json={"title": "测试项目"}).json()
    resp = client.post(
        f"/api/v1/projects/{proj['id']}/images",
        files={"file": ("desk.png", png, "image/png")},
    )
    return proj, resp


def _wait_job(client, job_id: str, tries: int = 20) -> dict:
    for _ in range(tries):
        job = client.get(f"/api/v1/jobs/{job_id}").json()
        if job["status"] in ("succeeded", "failed", "cancelled"):
            return job
    return job


def test_health_and_capabilities(client):
    h = client.get("/api/v1/health")
    assert h.status_code == 200 and h.json()["status"] == "ok"
    caps = client.get("/api/v1/capabilities").json()
    assert caps["run_mode"] == "mock"
    assert caps["detector"]["model_name"] == "mock-detector"
    assert "detect" in caps["features"]


def test_detect_flow_mock(client, sample_png):
    proj, up = _upload(client, sample_png)
    assert up.status_code == 200, up.text
    image_id = up.json()["image_asset_id"]
    assert up.json()["canonical_width"] == 64

    created = client.post(
        f"/api/v1/projects/{proj['id']}/jobs/detect", json={"image_asset_id": image_id}
    )
    assert created.status_code == 202
    job_id = created.json()["id"]

    job = _wait_job(client, job_id)
    assert job["status"] == "succeeded", job
    assert job["result"]["run_mode"] == "mock"
    assert len(job["detections"]) == 2

    # 契约一致性（G1）
    _validator().validate(job)

    # ID 守恒：再次查询 detection id 不变（H01 接口层体现）
    job2 = _wait_job(client, job_id)
    ids1 = sorted(d["id"] for d in job["detections"])
    ids2 = sorted(d["id"] for d in job2["detections"])
    assert ids1 == ids2 and len(set(ids1)) == len(ids1)


def test_asset_served(client, sample_png):
    _, up = _upload(client, sample_png)
    image_id = up.json()["image_asset_id"]
    got = client.get(f"/api/v1/assets/{image_id}")
    assert got.status_code == 200
    assert got.headers["content-type"] in ("image/png", "image/jpeg")
    assert len(got.content) > 0


def test_reject_disguised_image(client):
    proj = client.post("/api/v1/projects", json={}).json()
    resp = client.post(
        f"/api/v1/projects/{proj['id']}/images",
        files={"file": ("fake.png", b"this is not an image", "image/png")},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["code"] == "INVALID_IMAGE"
    assert body["request_id"]  # 统一错误对象含 request_id


def test_reject_unsupported_extension(client):
    proj = client.post("/api/v1/projects", json={}).json()
    resp = client.post(
        f"/api/v1/projects/{proj['id']}/images",
        files={"file": ("note.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 415
    assert resp.json()["code"] == "INVALID_IMAGE"


def test_real_mode_missing_weights_does_not_fallback(real_client, sample_png):
    proj, up = _upload(real_client, sample_png)
    caps = real_client.get("/api/v1/capabilities").json()
    assert caps["detector"]["available"] is False  # 如实标注不可用

    created = real_client.post(
        f"/api/v1/projects/{proj['id']}/jobs/detect",
        json={"image_asset_id": up.json()["image_asset_id"]},
    )
    job = _wait_job(real_client, created.json()["id"])
    assert job["status"] == "failed"
    assert job["error"]["code"] == "MODEL_UNAVAILABLE"
    assert job["detections"] == []  # 未静默产出 mock 结果
