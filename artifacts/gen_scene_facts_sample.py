"""生成 scene_facts 契约合法样例（可复现）。

用一个固定的规范场景跑 compute_scene_facts，把输出写到
contracts/samples/scene_facts.valid.json，避免手写样例与实现漂移。

Phase 4 阶段 B：样例含 object.attributes（颜色 + 几何 + 语义预留）。颜色需原图像素，
故这里合成一张**确定性纯色分区图**（每个物品框涂一种基本色），使样例展示真实色值而非
全 unknown；同图同框同结果，可复现。desk 视为全图 → bbox_image == bbox_desk。
语义属性恒 blocked（VL 凭据未到位），样例如实呈现 status=blocked、四项 null。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.understanding.scene_facts import SceneObject, compute_scene_facts  # noqa: E402

IMG_W = IMG_H = 200  # 合成原图尺寸（坐标 2 位小数 × 200 恒为整数，裁剪与涂色精确对齐）

# class_id 用 category_map version 2 索引（D011）：laptop=0/mouse=3/cup=7/book=5/pen=6。
# source 混用两路：微调检测器 yolov10:yolov10_desk_fine；开放词表 yolo-world
# （fusion 会把开放词表命中的 cup/pen 重映射到 v2 产品索引，故 class_id 与检测器路一致）。
# rgb 为合成图该框区域涂的纯色，用于展示真实色值（确定性、可复现）。
_SCENE_DEF = [
    # (object_id, class_name, bbox[=desk=image 归一化], class_id, rgb, kwargs)
    ("obj_laptop_1", "laptop", [0.30, 0.55, 0.70, 0.90], 0, (70, 72, 75),
     {"fixed": True, "source": "yolov10:yolov10_desk_fine"}),
    ("obj_mouse_1", "mouse", [0.74, 0.72, 0.84, 0.82], 3, (238, 238, 240),
     {"high_frequency": True, "source": "yolov10:yolov10_desk_fine"}),
    ("obj_cup_1", "cup", [0.10, 0.60, 0.18, 0.72], 7, (35, 95, 175),
     {"source": "yolo-world"}),
    ("obj_book_1", "book", [0.10, 0.10, 0.26, 0.24], 5, (176, 42, 55),
     {"source": "yolov10:yolov10_desk_fine"}),
    ("obj_book_2", "book", [0.28, 0.11, 0.42, 0.25], 5, (46, 140, 70),
     {"source": "yolov10:yolov10_desk_fine"}),
    ("obj_pen_1", "pen", [0.50, 0.15, 0.54, 0.30], 6, (225, 190, 30),
     {"source": "yolo-world"}),
]


def _build_scene():
    """构造 SceneObject 列表 + 合成原图（每框涂纯色；desk=全图 → bbox_image=bbox_desk）。"""
    img = Image.new("RGB", (IMG_W, IMG_H), (245, 245, 245))
    objs = []
    for oid, cname, bbox, cid, rgb, kw in _SCENE_DEF:
        x1, y1, x2, y2 = bbox
        img.paste(rgb, (int(x1 * IMG_W), int(y1 * IMG_H), int(x2 * IMG_W), int(y2 * IMG_H)))
        objs.append(SceneObject(oid, cname, list(bbox), class_id=cid,
                                bbox_image=list(bbox), **kw))
    return objs, img


def main() -> int:
    scene, img = _build_scene()
    facts = compute_scene_facts(scene, user_side="bottom", handedness="right",
                                mode="office", image=img)
    out = ROOT / "contracts" / "samples" / "scene_facts.valid.json"
    out.write_text(json.dumps(facts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    colors = {o["object_id"]: o["attributes"]["color"]["name"] for o in facts["objects"]}
    print(f"wrote {out} (object_count={facts['object_count']}, colors={colors})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
