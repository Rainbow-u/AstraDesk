"""YOLO-World 开放词表适配器真实冒烟验证（Phase 2）。

在一张 val 图上跑**真实主检测(微调 desk9) + 真实开放词表(YOLO-World) + 真实融合**，验证：
- 本地加载 weights/yolov8s-world.pt（不联网）；
- 返回带 source=yolo-world 的原始提示词类别框；
- 经 fusion.fuse 映射到产品类/other 后与**真实主检测**融合（重叠抑制主检测优先）。

主检测侧为真实 detector.detect_real(yolov10_desk9.pt)，**非合成框**（payload.primary_is_synthetic=false）。
证据写 artifacts/t_openvocab/smoke.json。默认 CPU；传 --device 0 在空闲 GPU 上测（6GB 可行性）。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

from packages.vision import detector, fusion, open_vocab  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", default="")
    ap.add_argument("--weights", default=str(ROOT / "weights" / "yolov8s-world.pt"))
    ap.add_argument("--primary-weights", default=str(ROOT / "weights" / "yolov10_desk9.pt"))
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--conf", type=float, default=0.15)
    ap.add_argument("--primary-conf", type=float, default=0.25)
    ap.add_argument("--out", default=str(ROOT / "artifacts" / "t_openvocab" / "smoke.json"))
    args = ap.parse_args()

    img_path = Path(args.image) if args.image else next(
        iter(sorted((ROOT / "data" / "desk9" / "val" / "images").glob("*.jpg"))))
    weights = Path(args.weights)
    primary_weights = Path(args.primary_weights)
    with Image.open(img_path) as im:
        img = im.convert("RGB")

    # 真实主检测（微调 desk9），非合成框
    prim = detector.detect_real(img, weights_path=primary_weights, device=args.device,
                                conf=args.primary_conf)
    t0 = time.perf_counter()
    ov = open_vocab.detect_open_vocab(img, weights_path=weights, device=args.device, conf=args.conf)
    elapsed = time.perf_counter() - t0

    fused = fusion.fuse(prim.detections, ov.detections, iou_thr=0.5)

    payload = {
        "image": img_path.name,
        "weights": weights.name,
        "weights_bytes": weights.stat().st_size if weights.exists() else None,
        "primary_weights": primary_weights.name,
        "primary_is_synthetic": False,  # 主检测为真实 detect_real 产出（非合成框）
        "device": args.device,
        "conf": args.conf,
        "primary_model": {"name": prim.model_name, "version": prim.model_version,
                          "run_mode": prim.run_mode},
        "primary_count": len(prim.detections),
        "primary": [{"class_id": d.class_id, "class_name": d.class_name,
                     "confidence": round(d.confidence, 4), "source": d.source}
                    for d in prim.detections],
        "open_vocab_model": {"name": ov.model_name, "version": ov.model_version},
        "open_vocab_raw_count": len(ov.detections),
        "open_vocab_raw": [{"class_name": d.class_name, "confidence": round(d.confidence, 4),
                            "source": d.source} for d in ov.detections],
        "fused_count": len(fused),
        # W-new-3/FR03：保留开放词表映射前的原始提示词名（other 可直接读出原本是什么，如 lamp/power bank/tissue）
        "fused": [{"class_id": d.class_id, "class_name": d.class_name,
                   "raw_class_name": getattr(d, "raw_class_name", "") or None,
                   "confidence": round(d.confidence, 4), "source": d.source} for d in fused],
        "added_by_openvocab": [{"class_id": d.class_id, "class_name": d.class_name,
                                "raw_class_name": getattr(d, "raw_class_name", "") or None,
                                "confidence": round(d.confidence, 4), "source": d.source}
                               for d in fused if d.source == "yolo-world"],
        "elapsed_seconds": round(elapsed, 3),
        "elapsed_fused_incl_load": round(time.perf_counter() - t0, 3),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"primary_count": payload["primary_count"],
                      "open_vocab_raw_count": payload["open_vocab_raw_count"],
                      "fused_count": payload["fused_count"],
                      "added_by_openvocab": len(payload["added_by_openvocab"]),
                      "elapsed_seconds": payload["elapsed_seconds"],
                      "device": args.device, "out": str(out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
