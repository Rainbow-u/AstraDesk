#!/usr/bin/env python3
"""在 data/desk9(9 类)上微调 YOLOv10，产物复制为 weights/yolov10_desk9.pt 并写训练报告。

6GB 显存安全配置：yolov10n 起始、imgsz=640、batch=8、AMP、patience 早停。
增强偏向凌乱鲁棒：mosaic/mixup/hsv/degrees/scale/fliplr。
"""
import json
import os
import shutil
import time

from ultralytics import YOLO

START = "/mnt/d/AstraDesk/weights/yolov10n.pt"
DATA = "/mnt/d/AstraDesk/data/desk9/data9.yaml"
OUTW = "/mnt/d/AstraDesk/weights/yolov10_desk9.pt"
RUNDIR = "/mnt/d/AstraDesk/runs/detect/astradesk_desk9"
REPORT = "/mnt/d/AstraDesk/artifacts/t_finetune/train_report.json"


def main():
    t0 = time.time()
    model = YOLO(START)
    res = model.train(
        data=DATA,
        epochs=100,
        imgsz=640,
        batch=8,
        device=0,
        amp=True,
        patience=20,
        workers=4,
        project="/mnt/d/AstraDesk/runs/detect",
        name="astradesk_desk9",
        exist_ok=True,
        mosaic=1.0,
        mixup=0.3,
        hsv_h=0.015,
        hsv_s=0.7,
        hsv_v=0.4,
        degrees=15.0,
        scale=0.5,
        fliplr=0.5,
        seed=42,
        verbose=True,
    )
    best = os.path.join(RUNDIR, "weights", "best.pt")
    shutil.copy(best, OUTW)
    metrics = getattr(res, "results_dict", {}) or {}
    report = {
        "model": "yolov10_desk9",
        "start_weights": START,
        "dataset": "data/desk9 (remapped YOLO-DeskDataset, 9 product classes)",
        "train_images": 1490,
        "val_images": 93,
        "epochs": 100,
        "imgsz": 640,
        "batch": 8,
        "device": 0,
        "amp": True,
        "patience": 20,
        "augmentation": "mosaic=1.0 mixup=0.3 hsv degrees=15 scale=0.5 fliplr=0.5",
        "elapsed_seconds": round(time.time() - t0, 1),
        "metrics": metrics,
        "best_weights": OUTW,
    }
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print("TRAIN_DONE", OUTW, "elapsed_s=", report["elapsed_seconds"])


if __name__ == "__main__":
    main()
