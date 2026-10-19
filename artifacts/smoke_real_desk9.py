#!/usr/bin/env python3
"""Phase 1/3 真实端到端冒烟：real 模式微调检测 → 确定性 facts → 模板 NL。

【历史脚本说明（Phase 4 后）】本脚本针对 desk9（9 类，version 1）编写，证据
 artifacts/t_finetune/smoke_real_desk9.json 已在 Phase 1/3 当时生成。Phase 4 阶段 A 后
 real 模式默认权重已改为 weights/yolov10_desk_fine.pt（24 类，version 2），故直接重跑
 本脚本会在下方 weights_path 断言处失败。 desk_fine 的等效冒烟见
 artifacts/smoke_real_desk_fine.py。如需重跑本历史脚本，须显式指定旧权重：
   ASTRADESK_YOLO_WEIGHTS=weights/yolov10_desk9.pt python artifacts/smoke_real_desk9.py
 （且 data/desk9/val/images 仍在）；下方断言有意保留为 Phase 1/3 的预期值。

证据目的（非 mock）：
- 确认 config.load_settings() 在 real 模式默认权重指向 weights/yolov10_desk9.pt；
- detector.detect_real 产出 9 产品类名 + source=yolov10:yolov10_desk9（FR03 可追溯）；
- 检测结果经 image_to_desk → compute_scene_facts → render_nl 跑通确定性 NL（不调 VL）；
- 输出证据到 artifacts/t_finetune/smoke_real_desk9.json。

在 desk9 val 图上跑（GPU 可用则用 GPU）。缺权重会抛 DetectorUnavailable（不静默回退）。
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

OUT = "/mnt/d/AstraDesk/artifacts/t_finetune/smoke_real_desk9.json"
VAL_IMG = "/mnt/d/AstraDesk/data/desk9/val/images"
N = 3


def main():
    os.environ.setdefault("ASTRADESK_RUN_MODE", "real")
    st = load_settings()
    assert st.run_mode == "real", st.run_mode
    assert st.weights_path.name == "yolov10_desk9.pt", st.weights_path

    stems = sorted(glob.glob(os.path.join(VAL_IMG, "*")))[:N]
    records = []
    for p in stems:
        im = Image.open(p).convert("RGB")
        res = detector.detect(im, run_mode="real", weights_path=st.weights_path,
                              device=st.detector_device, conf=st.detector_conf)
        # 全图当桌面（无用户标定桌面框时的冒烟近似）
        desk = [0.0, 0.0, 1.0, 1.0]
        objs = []
        for i, d in enumerate(res.detections):
            cname = d.class_name if d.class_name in PRODUCT_CLASSES else "other"
            bdesK = image_to_desk(d.bbox_image, desk)
            objs.append(SceneObject(object_id=f"{os.path.basename(p)}#{i}",
                                    class_name=cname, class_id=d.class_id,
                                    bbox_desk=bdesK, source=d.source))
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
            "all_source_finetuned": all(d.source == "yolov10:yolov10_desk9" for d in res.detections),
            "scene_object_count": facts["object_count"],
            "description_summary": desc["summary"],
            "description_text_head": desc["text"].splitlines()[0],
        })

    payload = {
        "run_mode": st.run_mode,
        "weights": str(st.weights_path),
        "note": "real 模式真实 GPU/CPU 推理，非 mock；全图当桌面为冒烟近似（无用户标定桌面框）",
        "records": records,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
