#!/usr/bin/env python3
"""Phase 4 阶段 B 真实端到端冒烟：real desk_fine 检测 → 关联原图取像素 → 确定性属性。

证据目的（非 mock）：
- detect(real, desk_fine) 产框后，用**同一张原图** + bbox_image 反归一化裁剪提取真实主色；
- 每个物体 attributes 齐全：color{name,rgb,hsv} + aspect_ratio/orientation/size_class（几何恒可派生）；
- semantic 恒 blocked（四字段 null），不因缺 VL 凭据编造语义（红线1/7）；
- 颜色确定性：同图同框两次提取结果完全一致（可复现）；
- facts 过 scene_facts.schema.json 校验；render_nl 描述融入“X色 + 竖放/横放 + 大/中/小号”。
- 输出证据到 artifacts/t_finetune/smoke_attributes_desk_fine.json。

缺权重会抛 DetectorUnavailable（不静默回退）。GPU 可用则用 GPU。
"""
import glob
import json
import os

import jsonschema
from PIL import Image

from packages.layout.coordinates import image_to_desk
from packages.understanding import render_nl, scene_facts
from packages.understanding.scene_facts import PRODUCT_CLASSES, SceneObject
from packages.vision import detector
from services.api.config import load_settings

OUT = "/mnt/d/AstraDesk/artifacts/t_finetune/smoke_attributes_desk_fine.json"
SCHEMA = "/mnt/d/AstraDesk/contracts/scene_facts.schema.json"
VAL_IMG = "/mnt/d/AstraDesk/data/desk_fine/val/images"
N = 4


def main():
    os.environ.setdefault("ASTRADESK_RUN_MODE", "real")
    st = load_settings()
    assert st.run_mode == "real", st.run_mode
    assert st.weights_path.name == "yolov10_desk_fine.pt", st.weights_path

    schema = json.loads(open(SCHEMA, encoding="utf-8").read())
    validator = jsonschema.Draft202012Validator(schema)

    stems = sorted(glob.glob(os.path.join(VAL_IMG, "*")))[:N]
    records = []
    for p in stems:
        im = Image.open(p).convert("RGB")
        res = detector.detect(im, run_mode="real", weights_path=st.weights_path,
                              device=st.detector_device, conf=st.detector_conf)
        desk = [0.0, 0.0, 1.0, 1.0]  # 全图当桌面（无用户标定桌面框时的冒烟近似）
        objs = []
        for i, d in enumerate(res.detections):
            cname = d.class_name if d.class_name in PRODUCT_CLASSES else "other"
            bdesk = image_to_desk(d.bbox_image, desk)
            objs.append(SceneObject(object_id=f"{os.path.basename(p)}#{i}",
                                    class_name=cname, class_id=d.class_id,
                                    bbox_desk=bdesk, bbox_image=list(d.bbox_image),
                                    source=d.source))
        # 关联原图取像素 → 颜色可提取；再跑一次验证确定性
        facts = scene_facts.compute_scene_facts(objs, image=im, user_side="bottom",
                                                handedness="right", mode="office")
        facts2 = scene_facts.compute_scene_facts(objs, image=im, user_side="bottom",
                                                 handedness="right", mode="office")
        validator.validate(facts)  # 带属性的事实过契约
        deterministic = json.dumps(facts, sort_keys=True) == json.dumps(facts2, sort_keys=True)
        desc = render_nl.render(facts)

        attrs = [o["attributes"] for o in facts["objects"]]
        records.append({
            "image": os.path.basename(p),
            "model_name": res.model_name,
            "run_mode": res.run_mode,
            "device": res.device,
            "object_count": facts["object_count"],
            "attributes": [{
                "object_id": o["object_id"],
                "class_name": o["class_name"],
                "color": o["attributes"]["color"],
                "orientation": o["attributes"]["orientation"],
                "size_class": o["attributes"]["size_class"],
                "aspect_ratio": o["attributes"]["aspect_ratio"],
                "semantic_status": o["attributes"]["semantic"]["status"],
            } for o in facts["objects"]],
            "colors_non_unknown": sum(1 for a in attrs if a["color"]["name"] != "unknown"),
            "all_geometry_present": all(
                {"aspect_ratio", "orientation", "size_class"} <= set(a) for a in attrs),
            "all_semantic_blocked": all(a["semantic"]["status"] == "blocked" for a in attrs),
            "deterministic": deterministic,
            "schema_valid": True,
            "description_summary": desc["summary"],
        })

    payload = {
        "run_mode": st.run_mode,
        "weights": str(st.weights_path),
        "note": "real 模式真实 GPU/CPU 推理 + 原图像素取色，非 mock；全图当桌面为冒烟近似",
        "records": records,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
