"""T02 真实桌面识别端到端验证（经完整 API 栈，非独立脚本）。

用 real 模式启动应用（TestClient 在进程内跑完整路由→服务→真实 YOLOv10 检测），
对 YOLO-DeskDataset 的一张真实 val 图执行：创建项目 → 上传 → 检测任务 → 查询结果。
保存结果 JSON 与叠框图作为证据。

诚实边界：yolov10n.pt 为 COCO 预训练，与数据集 80 桌面类别不同；本脚本只验证
"真实模型经产品 API 路径能跑出检测框并落库/符合契约"，不代表桌面类别精度（T14 微调）。
"""
from __future__ import annotations

import glob
import io
import json
import shutil
import sys
from pathlib import Path

ROOT = Path("/mnt/d/AstraDesk")
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from services.api.app import create_app  # noqa: E402
from services.api.config import Settings  # noqa: E402

OUT = ROOT / "artifacts" / "t02_detect"
DATA = OUT / "data"
WEIGHTS = ROOT / "weights" / "yolov10n.pt"
VAL_DIR = ROOT / "data" / "YOLO-DeskDataset" / "dataset" / "val" / "images"


def pick_image() -> Path:
    for pat in ("*.jpg", "*.jpeg", "*.png", "*.JPG"):
        hits = sorted(glob.glob(str(VAL_DIR / pat)))
        if hits:
            return Path(hits[0])
    raise SystemExit(f"no val image under {VAL_DIR}")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(parents=True, exist_ok=True)
    img_path = pick_image()

    settings = Settings(
        run_mode="real",
        db_url=f"sqlite:///{DATA / 't02.db'}",
        data_root=DATA,
        weights_path=WEIGHTS,
        detector_device="",
        detector_conf=0.25,
    )
    app = create_app(settings)
    with TestClient(app) as client:
        caps = client.get("/api/v1/capabilities").json()
        proj = client.post("/api/v1/projects", json={"title": "T02 真实检测"}).json()
        raw = img_path.read_bytes()
        up = client.post(
            f"/api/v1/projects/{proj['id']}/images",
            files={"file": (img_path.name, raw, "image/jpeg")},
        ).json()
        created = client.post(
            f"/api/v1/projects/{proj['id']}/jobs/detect",
            json={"image_asset_id": up["image_asset_id"]},
        )
        job_id = created.json()["id"]
        job = client.get(f"/api/v1/jobs/{job_id}").json()

    # 叠框图
    with Image.open(io.BytesIO(raw)) as im:
        im = im.convert("RGB")
        w, h = im.size
        draw = ImageDraw.Draw(im)
        for d in job.get("detections", []):
            x1, y1, x2, y2 = d["bbox_image"]
            draw.rectangle([x1 * w, y1 * h, x2 * w, y2 * h], outline=(255, 80, 80), width=3)
            draw.text((x1 * w + 4, max(y1 * h - 14, 0)),
                      f"{d['class_name']} {d['confidence']:.2f}", fill=(255, 255, 0))
        im.save(OUT / "annotated.jpg", format="JPEG", quality=90)

    evidence = {
        "source_image": str(img_path),
        "source_image_copied_to": str(OUT / "source.jpg"),
        "capabilities": caps,
        "upload": up,
        "job": job,
    }
    shutil.copy(img_path, OUT / "source.jpg")
    (OUT / "result.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=== capabilities ===")
    print(json.dumps(caps, ensure_ascii=False))
    print("=== job summary ===")
    print("status:", job["status"])
    print("run_mode:", (job.get("result") or {}).get("run_mode"))
    print("device:", (job.get("result") or {}).get("device"))
    print("elapsed_seconds:", (job.get("result") or {}).get("elapsed_seconds"))
    print("detections:", len(job.get("detections", [])))
    for d in job.get("detections", []):
        print(f"  - {d['class_name']}({d['class_id']}) {d['confidence']:.3f} bbox={[round(v,3) for v in d['bbox_image']]}")
    print("error:", job.get("error"))


if __name__ == "__main__":
    main()
