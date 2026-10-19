"""开放词表融合在检测服务中的接入测试（Phase 2）。

用 monkeypatch 隔离真实模型/GPU，验证 service.process_detect_job 的两条关键路径：
- real + openvocab_enabled：微调框与开放词表框融合，result_json 记录 open_vocab/fusion_iou；
- open-vocab 不可用（缺权重/依赖）：任务失败 MODEL_UNAVAILABLE，不静默跳过、不产出结果（约定1）。
"""
from __future__ import annotations

import io
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from packages.vision import detector, open_vocab
from packages.vision.detector import Detection, DetectionResult, DetectorUnavailable
from services.api.app import create_app
from services.api.config import Settings


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), (120, 160, 200)).save(buf, format="PNG")
    return buf.getvalue()


def _real_openvocab_client(tmp_path: Path) -> TestClient:
    data_root = tmp_path / "data"
    data_root.mkdir(parents=True, exist_ok=True)
    settings = Settings(
        run_mode="real",
        db_url=f"sqlite:///{data_root / 'test.db'}",
        data_root=data_root,
        weights_path=tmp_path / "yolov10_desk_fine.pt",
        detector_device="",
        detector_conf=0.25,
        openvocab_weights=tmp_path / "yolov8s-world.pt",
        openvocab_enabled=True,
        openvocab_conf=0.15,
        fusion_iou=0.5,
    )
    return TestClient(create_app(settings))


def _result(dets, model_name="yolov10_desk_fine"):
    return DetectionResult(model_name=model_name, model_version=f"{model_name}.pt",
                           run_mode="real", elapsed_seconds=0.01, detections=dets,
                           image_width=64, image_height=48, device="cpu")


def _run_detect(client) -> dict:
    proj = client.post("/api/v1/projects", json={"title": "融合"}).json()
    up = client.post(f"/api/v1/projects/{proj['id']}/images",
                     files={"file": ("desk.png", _png(), "image/png")})
    created = client.post(f"/api/v1/projects/{proj['id']}/jobs/detect",
                          json={"image_asset_id": up.json()["image_asset_id"]})
    job_id = created.json()["id"]
    for _ in range(20):
        job = client.get(f"/api/v1/jobs/{job_id}").json()
        if job["status"] in ("succeeded", "failed", "cancelled"):
            return job
    return job


def test_openvocab_fusion_merges_and_records(tmp_path, monkeypatch):
    monkeypatch.setattr(detector, "detect",
                        lambda *a, **k: _result([Detection(0, "laptop", 0.8, [0.1, 0.1, 0.5, 0.5],
                                                           source="yolov10:yolov10_desk_fine")]))
    monkeypatch.setattr(open_vocab, "detect_open_vocab",
                        lambda *a, **k: _result([Detection(5, "pen", 0.4, [0.7, 0.7, 0.9, 0.9],
                                                           source="yolo-world")],
                                                model_name="yolo-world"))
    client = _real_openvocab_client(tmp_path)
    with client:
        job = _run_detect(client)
    assert job["status"] == "succeeded", job
    names = sorted(d["class_name"] for d in job["detections"])
    assert names == ["laptop", "pen"]  # 微调框 + 开放词表补框
    sources = {d["class_name"]: d["source"] for d in job["detections"]}
    assert sources["pen"] == "yolo-world"
    assert sources["laptop"] == "yolov10:yolov10_desk_fine"
    # W-new-3：开放词表原始提示词名经 API 回写（FR03 原始类可追溯）；主检测无原始名
    raw_names = {d["class_name"]: d.get("raw_class_name") for d in job["detections"]}
    assert raw_names["pen"] == "pen"
    assert raw_names["laptop"] in (None, "")
    assert job["result"]["open_vocab"]["model_name"] == "yolo-world"
    assert job["result"]["fusion_iou"] == 0.5


def test_openvocab_unavailable_fails_without_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(detector, "detect",
                        lambda *a, **k: _result([Detection(0, "laptop", 0.8, [0.1, 0.1, 0.5, 0.5],
                                                           source="yolov10:yolov10_desk_fine")]))

    def _boom(*a, **k):
        raise DetectorUnavailable("open-vocab weights not found")

    monkeypatch.setattr(open_vocab, "detect_open_vocab", _boom)
    client = _real_openvocab_client(tmp_path)
    with client:
        job = _run_detect(client)
    assert job["status"] == "failed"
    assert job["error"]["code"] == "MODEL_UNAVAILABLE"
    assert job["detections"] == []  # 未静默跳过开放词表、未产出半成品


def test_mock_mode_skips_openvocab(tmp_path, monkeypatch):
    """mock 模式（is_real=False）不触发开放词表，即便 enabled 也不应调用。"""
    called = {"ov": False}

    def _ov(*a, **k):
        called["ov"] = True
        return _result([], model_name="yolo-world")

    monkeypatch.setattr(open_vocab, "detect_open_vocab", _ov)
    data_root = tmp_path / "data"
    data_root.mkdir(parents=True, exist_ok=True)
    settings = Settings(run_mode="mock", db_url=f"sqlite:///{data_root / 'test.db'}",
                        data_root=data_root, weights_path=tmp_path / "nope.pt",
                        detector_device="", detector_conf=0.25, openvocab_enabled=True)
    client = TestClient(create_app(settings))
    with client:
        job = _run_detect(client)
    assert job["status"] == "succeeded"
    assert called["ov"] is False
    assert job["result"]["open_vocab"] is None


def test_capabilities_open_vocab_only_advertised_when_weights_exist(tmp_path):
    """W7：启用但权重缺失时不得把 open_vocab 当作可用特性上报（available=False、不入 features）；
    权重存在时才 advertise。"""
    client = _real_openvocab_client(tmp_path)  # openvocab_enabled=True，但权重文件不存在
    with client:
        caps = client.get("/api/v1/capabilities").json()
    assert caps["open_vocab"]["enabled"] is True
    assert caps["open_vocab"]["available"] is False
    assert "open_vocab" not in caps["features"]  # 缺权重会使检测 MODEL_UNAVAILABLE，不当可用能力

    # 权重到位后（同路径创建文件）才 advertise
    (tmp_path / "yolov8s-world.pt").write_bytes(b"stub")
    client2 = _real_openvocab_client(tmp_path)
    with client2:
        caps2 = client2.get("/api/v1/capabilities").json()
    assert caps2["open_vocab"]["available"] is True
    assert "open_vocab" in caps2["features"]
