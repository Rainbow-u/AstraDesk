#!/usr/bin/env python3
"""在 data/desk_fine(23 训练类, version 2 映射)上从 COCO 迁移学习重训 YOLOv10。

类数由 9→23（检测头重构），故从 yolov10n.pt(COCO) 起训，不从 desk9 续训。
6GB 显存安全配置：imgsz=640、batch=8、AMP、patience 早停。增强偏向凌乱鲁棒。
产物 best.pt → weights/yolov10_desk_fine.pt，训练报告写 artifacts/t_finetune/train_report_desk_fine.json。

试跑：ASTRADESK_EPOCHS=2 ASTRADESK_TRIAL=1 python tools/train_desk_fine.py（不落正式权重/报告）。
"""
import json
import os
import shutil
import time

from ultralytics import YOLO

PROJECT_ROOT = "/mnt/d/AstraDesk"
START = os.path.join(PROJECT_ROOT, "weights", "yolov10n.pt")
DATA = os.path.join(PROJECT_ROOT, "data", "desk_fine", "data_fine.yaml")
OUTW = os.path.join(PROJECT_ROOT, "weights", "yolov10_desk_fine.pt")
RUNNAME = "astradesk_desk_fine"
RUNDIR = os.path.join(PROJECT_ROOT, "runs", "detect", RUNNAME)
REPORT = os.path.join(PROJECT_ROOT, "artifacts", "t_finetune", "train_report_desk_fine.json")

EPOCHS = int(os.environ.get("ASTRADESK_EPOCHS", "100"))
TRIAL = os.environ.get("ASTRADESK_TRIAL", "") == "1"


def main():
    t0 = time.time()
    model = YOLO(START)
    res = model.train(
        data=DATA,
        epochs=EPOCHS,
        imgsz=640,
        batch=8,
        device=0,
        amp=True,
        patience=20,
        workers=4,
        project=os.path.join(PROJECT_ROOT, "runs", "detect"),
        name=RUNNAME,
        exist_ok=True,
        mosaic=1.0,
        mixup=0.3,
        copy_paste=0.1,
        hsv_h=0.015,
        hsv_s=0.7,
        hsv_v=0.4,
        degrees=15.0,
        scale=0.5,
        fliplr=0.5,
        seed=42,
        verbose=True,
    )
    elapsed = round(time.time() - t0, 1)
    if TRIAL:
        print("TRIAL_DONE epochs=", EPOCHS, "elapsed_s=", elapsed, "(未落正式权重/报告)")
        return
    best = os.path.join(RUNDIR, "weights", "best.pt")
    shutil.copy(best, OUTW)
    metrics = getattr(res, "results_dict", {}) or {}
    report = {
        "model": "yolov10_desk_fine",
        "start_weights": START,
        "dataset": "data/desk_fine (remapped YOLO-DeskDataset, version 2, 23 trained classes + other)",
        "nc": 23,
        "train_images": 1549,
        "val_images": 97,
        "epochs": EPOCHS,
        "imgsz": 640,
        "batch": 8,
        "device": 0,
        "amp": True,
        "patience": 20,
        "augmentation": "mosaic=1.0 mixup=0.3 copy_paste=0.1 hsv degrees=15 scale=0.5 fliplr=0.5",
        "elapsed_seconds": elapsed,
        "metrics": metrics,
        "best_weights": OUTW,
    }
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print("TRAIN_DONE", OUTW, "elapsed_s=", elapsed)


if __name__ == "__main__":
    main()
