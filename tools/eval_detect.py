#!/usr/bin/env python3
"""Track1 评测：在重映射后的 desk9 val 上对比 基线(COCO yolov10n) vs 微调(yolov10_desk9)。

- 微调模型另用 ultralytics val 出 mAP50/mAP50-95（原生 9 类词表）。
- 词表缺口对比：两模型都映射到 9 产品类后，对同一 GT 算每类 Precision/Recall@conf。
  基线 COCO 无 pen 等类，其 recall 直接暴露词表缺口。
- 诚实标注：val 仅 93 图、数据集干净偏置、含增强重复(可能泄漏)，数字仅供相对比较。
输出 artifacts/t_finetune/eval_track1.json。
"""
import glob
import json
import os
from collections import defaultdict

from PIL import Image
from ultralytics import YOLO

DATA9 = "/mnt/d/AstraDesk/data/desk9/data9.yaml"
VAL_IMG = "/mnt/d/AstraDesk/data/desk9/val/images"
VAL_LAB = "/mnt/d/AstraDesk/data/desk9/val/labels"
BASELINE = "/mnt/d/AstraDesk/weights/yolov10n.pt"
FINETUNED = "/mnt/d/AstraDesk/weights/yolov10_desk9.pt"
REPORT = "/mnt/d/AstraDesk/artifacts/t_finetune/eval_track1.json"
CONF = 0.25
IOU = 0.5

PRODUCT = ["laptop", "monitor", "keyboard", "mouse", "book", "pen", "cup", "bottle", "mobile_phone"]
# 基线 COCO 名 -> 产品类（COCO 无 pen；monitor 借 tv）
COCO2PRODUCT = {
    "laptop": "laptop", "tv": "monitor", "keyboard": "keyboard", "mouse": "mouse",
    "book": "book", "cup": "cup", "wine glass": "cup", "bottle": "bottle",
    "cell phone": "mobile_phone",
}


def iou(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    ua = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - inter
    return inter / ua if ua > 0 else 0.0


def load_gt():
    gt = {}
    for lp in sorted(glob.glob(os.path.join(VAL_LAB, "*.txt"))):
        stem = os.path.splitext(os.path.basename(lp))[0]
        boxes = []
        for ln in open(lp, encoding="utf-8").read().strip().splitlines():
            r = ln.split()
            if len(r) < 5:
                continue
            c = int(r[0])
            cx, cy, w, h = map(float, r[1:5])
            boxes.append((c, [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]))
        if boxes:
            gt[stem] = boxes
    return gt


def run_model(weights, name_map, native_product):
    """返回 {stem: [(product_class_idx, conf, xyxy)]}。native_product=True 时模型名即产品类。"""
    model = YOLO(weights)
    stems = sorted(gt_stems())
    out = {}
    for stem in stems:
        imgp = find_image(stem)
        if not imgp:
            continue
        im = Image.open(imgp).convert("RGB")
        w, h = im.size
        preds = model.predict(im, verbose=False, conf=CONF)
        boxes = preds[0].boxes
        items = []
        for i in range(len(boxes)):
            cid = int(boxes.cls[i])
            conf = float(boxes.conf[i])
            xy = boxes.xyxy[i].tolist()
            xyxy = [xy[0] / w, xy[1] / h, xy[2] / w, xy[3] / h]
            if native_product:
                pname = model.names.get(cid, "")
                pidx = PRODUCT.index(pname) if pname in PRODUCT else -1
            else:
                cname = model.names.get(cid, "")
                pname = name_map.get(cname)
                pidx = PRODUCT.index(pname) if pname else -1
            if pidx >= 0:
                items.append((pidx, conf, xyxy))
        out[stem] = items
    return out


def gt_stems():
    return [os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(VAL_LAB, "*.txt"))]


def find_image(stem):
    for ext in ("jpg", "jpeg", "png", "JPG", "JPEG", "PNG"):
        c = os.path.join(VAL_IMG, stem + "." + ext)
        if os.path.exists(c):
            return c
    return None


def evaluate(preds, gt):
    stats = {p: {"tp": 0, "fp": 0, "fn": 0} for p in range(len(PRODUCT))}
    for stem, gboxes in gt.items():
        pitems = preds.get(stem, [])
        matched = set()
        for c, gxy in gboxes:
            best = None
            for j, (pc, conf, pxy) in enumerate(pitems):
                if pc != c or j in matched:
                    continue
                v = iou(gxy, pxy)
                if v >= IOU and (best is None or v > best[0]):
                    best = (v, j)
            if best:
                matched.add(best[1])
                stats[c]["tp"] += 1
            else:
                stats[c]["fn"] += 1
        for j, (pc, conf, pxy) in enumerate(pitems):
            if j not in matched:
                stats[pc]["fp"] += 1
    per = {}
    for c in range(len(PRODUCT)):
        s = stats[c]
        prec = s["tp"] / (s["tp"] + s["fp"]) if (s["tp"] + s["fp"]) else 0.0
        rec = s["tp"] / (s["tp"] + s["fn"]) if (s["tp"] + s["fn"]) else 0.0
        per[PRODUCT[c]] = {"precision": round(prec, 3), "recall": round(rec, 3),
                           "tp": s["tp"], "fp": s["fp"], "fn": s["fn"]}
    return per


def main():
    gt = load_gt()
    report = {"val_images": len(gt), "conf": CONF, "iou": IOU,
              "caveats": ["val 仅 93 图", "数据集干净桌面偏置", "含增强重复、无会话分组、可能泄漏，数字仅供相对比较"]}

    if os.path.exists(FINETUNED):
        ft = YOLO(FINETUNED)
        vr = ft.val(data=DATA9, device=0, verbose=False)
        rd = getattr(vr, "results_dict", {}) or {}
        report["finetuned_map"] = {
            "mAP50": rd.get("metrics/mAP50(B)"),
            "mAP50-95": rd.get("metrics/mAP50-95(B)"),
            "precision": rd.get("metrics/precision(B)"),
            "recall": rd.get("metrics/recall(B)"),
        }
        preds_ft = run_model(FINETUNED, None, native_product=True)
        report["finetuned_per_class"] = evaluate(preds_ft, gt)
    else:
        report["finetuned_map"] = None
        report["finetuned_per_class"] = None
        report["note"] = "yolov10_desk9.pt 尚不存在（训练未完成），跳过微调侧评测"

    preds_base = run_model(BASELINE, COCO2PRODUCT, native_product=False)
    report["baseline_coco_per_class"] = evaluate(preds_base, gt)

    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
