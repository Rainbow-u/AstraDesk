#!/usr/bin/env python3
"""Phase 4 阶段 A 真实端到端冒烟：real 模式 desk_fine(23类) 检测 → 确定性 facts → 模板 NL。

证据目的（非 mock）：
- 确认 config.load_settings() 在 real 模式默认权重指向 weights/yolov10_desk_fine.pt；
- detector.detect_real 产出 24 类词表内的细类名 + source=yolov10:yolov10_desk_fine（FR03 可追溯）；
- 检测结果经 image_to_desk → compute_scene_facts → render_nl 跑通确定性 NL（不调 VL）；
- 校验 scene_facts 的 PRODUCT_CLASSES 已含细类（不因新类名报 SceneFactsError）；
- 输出证据到 artifacts/t_finetune/smoke_real_desk_fine.json。

在 desk_fine val 图上跑（GPU 可用则用 GPU）。缺权重会抛 DetectorUnavailable（不静默回退）。
"""
import glob
import json
import os

from PIL import Image

from packages.layout.coordinates import image_to_desk
from packages.understanding import render_nl, scene_facts
from packages.understanding.scene_facts import PRODUCT_CLASSES, SceneObject
from packages.vision import detector
from services.api.config import load_settings

OUT = "/mnt/d/AstraDesk/artifacts/t_finetune/smoke_real_desk_fine.json"
VAL_IMG = "/mnt/d/AstraDesk/data/desk_fine/val/images"
N = 4
FINE_CLASSES = {"thermos_cup", "plastic_cup", "disposable_cup", "plastic_bottle",
                "squeeze_bottle", "can", "waterpot", "cable", "charger", "tissue",
                "paper", "lamp", "headphones", "mouse_pad"}


def main():
    os.environ.setdefault("ASTRADESK_RUN_MODE", "real")
    st = load_settings()
    assert st.run_mode == "real", st.run_mode
    assert st.weights_path.name == "yolov10_desk_fine.pt", st.weights_path

    stems = sorted(glob.glob(os.path.join(VAL_IMG, "*")))[:N]
    records = []
    seen_fine = set()
    for p in stems:
        im = Image.open(p).convert("RGB")
        res = detector.detect(im, run_mode="real", weights_path=st.weights_path,
                              device=st.detector_device, conf=st.detector_conf)
        # 全图当桌面（无用户标定桌面框时的冒烟近似）
        desk = [0.0, 0.0, 1.0, 1.0]
        objs = []
        for i, d in enumerate(res.detections):
            cname = d.class_name if d.class_name in PRODUCT_CLASSES else "other"
            if cname in FINE_CLASSES:
                seen_fine.add(cname)
            bdesk = image_to_desk(d.bbox_image, desk)
            objs.append(SceneObject(object_id=f"{os.path.basename(p)}#{i}",
                                    class_name=cname, class_id=d.class_id,
                                    bbox_desk=bdesk, source=d.source))
        facts = scene_facts.compute_scene_facts(objs, user_side="bottom",
                                                handedness="right", mode="office")
        desc = render_nl.render(facts)
        records.append({
            "image": os.path.basename(p),
            "model_name": res.model_name,
            "run_mode": res.run_mode,
            "device": res.device,
            "elapsed_seconds": round(res.elapsed_seconds, 3),
            "detections": [{"class_id": d.class_id, "class_name": d.class_name,
                            "confidence": round(d.confidence, 3), "source": d.source}
                           for d in res.detections],
            "all_names_in_product_vocab": all(d.class_name in PRODUCT_CLASSES for d in res.detections),
            "all_source_finetuned": all(d.source == "yolov10:yolov10_desk_fine" for d in res.detections),
            "scene_object_count": facts["object_count"],
            "description_summary": desc["summary"],
            "description_text_head": desc["text"].splitlines()[0],
        })

    payload = {
        "run_mode": st.run_mode,
        "weights": str(st.weights_path),
        "note": "real 模式真实 GPU/CPU 推理，非 mock；全图当桌面为冒烟近似（无用户标定桌面框）",
        "fine_classes_seen": sorted(seen_fine),
        "records": records,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
