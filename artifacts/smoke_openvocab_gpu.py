#!/usr/bin/env python3
"""Phase 2：YOLO-World 在 6GB GPU 上的推理可行性实测（训练释放显存后）。

测 device=0 上开放词表检测的峰值显存与耗时，判断 6GB 是否可行；证据写
artifacts/t_openvocab/gpu_feasibility.json。缺权重抛 DetectorUnavailable（不静默）。
"""
import glob
import json
import os
import time
from pathlib import Path

from PIL import Image

from packages.vision import open_vocab

WEIGHTS = "/mnt/d/AstraDesk/weights/yolov8s-world.pt"
VAL_IMG = "/mnt/d/AstraDesk/data/desk9/val/images"
OUT = "/mnt/d/AstraDesk/artifacts/t_openvocab/gpu_feasibility.json"


def main():
    import torch
    from services.api.config import load_settings

    st = load_settings()
    img = sorted(glob.glob(os.path.join(VAL_IMG, "*")))[0]
    im = Image.open(img).convert("RGB")

    assert torch.cuda.is_available(), "CUDA 不可用，无法做 GPU 可行性实测"
    torch.cuda.reset_peak_memory_stats()
    dev = "0"

    t0 = time.perf_counter()
    res = open_vocab.detect_open_vocab(im, weights_path=Path(WEIGHTS),
                                       device=dev, conf=st.openvocab_conf)
    first = time.perf_counter() - t0
    # 第二次（热）
    t1 = time.perf_counter()
    res2 = open_vocab.detect_open_vocab(im, weights_path=Path(WEIGHTS),
                                        device=dev, conf=st.openvocab_conf)
    second = time.perf_counter() - t1

    peak_alloc = torch.cuda.max_memory_allocated() / (1024 ** 3)
    peak_resv = torch.cuda.max_memory_reserved() / (1024 ** 3)
    total = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)

    payload = {
        "device": "cuda:0",
        "gpu_total_gib": round(total, 3),
        "weights": WEIGHTS,
        "image": os.path.basename(img),
        "raw_detections": len(res.detections),
        "cold_elapsed_seconds": round(first, 3),
        "warm_elapsed_seconds": round(second, 3),
        "peak_allocated_gib": round(peak_alloc, 3),
        "peak_reserved_gib": round(peak_resv, 3),
        "fits_6gb": peak_resv < 5.5,
        "names": sorted({d.class_name for d in res2.detections}),
        "note": "峰值显存为 YOLO-World 推理本身；系统/桌面另占约 2.6GiB，实际可用需扣除。",
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
