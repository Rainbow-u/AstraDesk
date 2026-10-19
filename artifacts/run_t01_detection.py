"""T01 真实检测验证脚本。

用本地 YOLOv10n 权重在 YOLO-DeskDataset 的一张真实 val 图上做一次 GPU 推理，
记录模型版本、类别表、检测结果、耗时与显存，保存标注图与 JSON 证据。

诚实边界：yolov10n.pt 为 COCO 预训练（80 个 COCO 类），与 YOLO-DeskDataset 的
80 个桌面类别标签集不同。本脚本只验证"真实模型能在真实图上跑出检测框"，
不验证桌面数据集类别精度（那属于 T14 微调）。COCO 与桌面词表的重叠类
（laptop/mouse/keyboard/cell phone/book/bottle/cup/tv 等）可能命中。
"""
import json, glob, time, platform
from pathlib import Path
import torch
from ultralytics import YOLO, settings

settings.update({"sync": False})  # 关闭遥测/联网同步，避免触发被墙的网络请求

ROOT = Path("/mnt/d/AstraDesk")
WEIGHTS = ROOT / "weights" / "yolov10n.pt"
VAL_IMG_DIR = ROOT / "data" / "YOLO-DeskDataset" / "dataset" / "val" / "images"
OUT_DIR = ROOT / "artifacts" / "t01_detection"
OUT_DIR.mkdir(parents=True, exist_ok=True)

imgs = sorted(glob.glob(str(VAL_IMG_DIR / "*")))
assert imgs, "no val images found"
img_path = imgs[0]

device = "cuda:0" if torch.cuda.is_available() else "cpu"
model = YOLO(str(WEIGHTS))

t0 = time.time()
results = model.predict(source=img_path, device=device, verbose=False)
infer_s = time.time() - t0

r = results[0]
names = model.names
dets = []
if r.boxes is not None:
    for b in r.boxes:
        cls_id = int(b.cls.item())
        dets.append({
            "class_id": cls_id,
            "class_name": names.get(cls_id, str(cls_id)),
            "confidence": round(float(b.conf.item()), 4),
            "bbox_xyxy_px": [round(float(v), 1) for v in b.xyxy[0].tolist()],
        })

annotated = OUT_DIR / (Path(img_path).stem + "_pred.jpg")
r.save(filename=str(annotated))

vr = None
if device.startswith("cuda"):
    vr = {
        "max_mem_allocated_mib": round(torch.cuda.max_memory_allocated(0) / 1024**2, 2),
        "device_name": torch.cuda.get_device_name(0),
    }

summary = {
    "task": "T01_detection_verification",
    "model_file": WEIGHTS.name,
    "model_class": "YOLOv10n (ultralytics)",
    "pretrained_on": "COCO (80 classes) - not YOLO-DeskDataset desk classes",
    "device": device,
    "torch_version": torch.__version__,
    "python": platform.python_version(),
    "image": Path(img_path).name,
    "image_size_wh": list(r.orig_shape[::-1]),
    "num_detections": len(dets),
    "num_classes_available": len(names),
    "inference_seconds_first_call_incl_load": round(infer_s, 3),
    "detections": dets,
    "vram": vr,
    "annotated_output": str(annotated.relative_to(ROOT)),
    "license_note": "YOLOv10/ultralytics weights+code are AGPL-3.0; commercial/closed distribution needs license review or enterprise license.",
    "honesty_note": "Proves a real model ran real inference and produced boxes; does NOT prove desk-dataset class accuracy (evaluated after T14 fine-tuning).",
}
(OUT_DIR / "result.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))
