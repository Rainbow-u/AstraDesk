#!/usr/bin/env python3
"""Track1b 评测：类别细化前后对比 —— 旧 desk9(9类) vs 新 desk_fine(23训练类)。

产出三部分证据，全部落 artifacts/t_finetune/eval_track1b.json：
1. desk_fine 原生 val（data_fine.yaml，97 图 / 23 类）：mAP50、mAP50-95、每类 P/R/mAP/support；
2. 细类分化质量：cup 家族(cup/thermos_cup/plastic_cup/disposable_cup)、bottle 家族
   (bottle/plastic_bottle/squeeze_bottle/can/waterpot) 各自 P/R + 家族内混淆（取自原生混淆矩阵）；
3. 父类聚合对比：在 desk9 val(93) 这一共同基准上，把 desk_fine 细类预测聚合回 cup/bottle 父类，
   与 desk9 直接输出的 cup/bottle 比 P/R，确认细化未显著掉总召回。

诚实标注：val 干净偏置、含增强重复、无会话分组、可能泄漏；cup/bottle 家族细类在 val 上 support 极小
（如 can/waterpot/disposable_cup 仅个位数），其每类 P/R 统计噪声大，数字仅供相对比较，不作绝对声称。
"""
import glob
import json
import os

from PIL import Image
from ultralytics import YOLO

ROOT = "/mnt/d/AstraDesk"
DATA_FINE = f"{ROOT}/data/desk_fine/data_fine.yaml"
FINE_WEIGHTS = f"{ROOT}/weights/yolov10_desk_fine.pt"
DESK9_WEIGHTS = f"{ROOT}/weights/yolov10_desk9.pt"
DESK9_VAL_IMG = f"{ROOT}/data/desk9/val/images"
DESK9_VAL_LAB = f"{ROOT}/data/desk9/val/labels"
REPORT = f"{ROOT}/artifacts/t_finetune/eval_track1b.json"
CONF = 0.25
IOU = 0.5

CUP_FAMILY = ("cup", "thermos_cup", "plastic_cup", "disposable_cup")
BOTTLE_FAMILY = ("bottle", "plastic_bottle", "squeeze_bottle", "can", "waterpot")


def parent_of(name):
    """细类名 -> 父类名（cup/bottle）；非杯瓶类返回 None（父类聚合对比只关心杯瓶）。"""
    if name in CUP_FAMILY:
        return "cup"
    if name in BOTTLE_FAMILY:
        return "bottle"
    return None


def iou(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    ua = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - inter
    return inter / ua if ua > 0 else 0.0


# ---------------------------------------------------------------- Part 1&2: desk_fine native val
def fine_native_val(model):
    """在 data_fine.yaml 上跑原生 val，返回 mAP 概览、每类指标、cup/bottle 家族混淆。

    不传 conf/iou → 用 ultralytics 默认（conf=0.001，跨全置信度算 PR 曲线），
    与 Phase 1 desk9 的 `ft.val(data=DATA9)` 方法一致，保证 mAP 可直接对比；
    每类 P/R 为 ultralytics 标准工作点（最大 F1），非固定阈值。
    """
    vr = model.val(data=DATA_FINE, device=0, verbose=False)
    rd = getattr(vr, "results_dict", {}) or {}
    names = model.names
    overview = {
        "mAP50": rd.get("metrics/mAP50(B)"),
        "mAP50-95": rd.get("metrics/mAP50-95(B)"),
        "precision": rd.get("metrics/precision(B)"),
        "recall": rd.get("metrics/recall(B)"),
    }
    box = vr.box
    per_class = {}
    ap_idx = list(getattr(box, "ap_class_index", []))
    nt_per = getattr(box, "nt_per_class", None)
    for i, cidx in enumerate(ap_idx):
        nm = names.get(int(cidx), str(int(cidx)))
        entry = {
            "precision": round(float(box.p[i]), 3),
            "recall": round(float(box.r[i]), 3),
            "mAP50": round(float(box.ap50[i]), 3),
            "mAP50-95": round(float(box.ap[i]), 3),
        }
        if nt_per is not None:
            try:
                entry["support"] = int(nt_per[int(cidx)])
            except Exception:
                pass
        per_class[nm] = entry
    # 未出现在 ap_class_index 的类（val 无 GT 或全漏）标 support=0，如实反映长尾
    for cidx, nm in names.items():
        if nm not in per_class:
            per_class[nm] = {"precision": 0.0, "recall": 0.0, "mAP50": 0.0, "mAP50-95": 0.0,
                             "support": 0, "note": "val 无该类 GT 或全漏，指标为 0"}
    families = {
        "cup_family": {n: per_class.get(n) for n in CUP_FAMILY},
        "bottle_family": {n: per_class.get(n) for n in BOTTLE_FAMILY},
    }
    families["cup_family_confusion"] = _family_confusion(vr, names, CUP_FAMILY)
    families["bottle_family_confusion"] = _family_confusion(vr, names, BOTTLE_FAMILY)
    return overview, per_class, families


def _family_confusion(vr, names, family):
    """从原生混淆矩阵抽取家族内(含家族->其它类/背景)的预测计数。matrix[pred, gt]（ultralytics 约定）。"""
    cm = getattr(vr, "confusion_matrix", None)
    mat = getattr(cm, "matrix", None) if cm is not None else None
    if mat is None:
        return None
    idxs = [i for i, n in names.items() if n in family]
    out = {}
    for gt_i in idxs:
        gt_name = names[gt_i]
        row = {}
        for pred_i in range(mat.shape[0]):
            v = float(mat[pred_i, gt_i])
            if v <= 0:
                continue
            pred_name = "background(FN)" if pred_i == mat.shape[0] - 1 else names.get(pred_i, str(pred_i))
            row[pred_name] = round(v, 1)
        out[gt_name] = row
    return out


# ---------------------------------------------------------------- Part 3: parent aggregation on desk9 val
def _find_image(stem):
    for ext in ("jpg", "jpeg", "png", "JPG", "JPEG", "PNG"):
        c = os.path.join(DESK9_VAL_IMG, stem + "." + ext)
        if os.path.exists(c):
            return c
    return None


def load_parent_gt(names9):
    """desk9 val 标签 -> {stem: [(parent, xyxy_norm)]}，仅保留 cup/bottle 父类框。"""
    gt = {}
    for lp in sorted(glob.glob(os.path.join(DESK9_VAL_LAB, "*.txt"))):
        stem = os.path.splitext(os.path.basename(lp))[0]
        boxes = []
        for ln in open(lp, encoding="utf-8").read().strip().splitlines():
            r = ln.split()
            if len(r) < 5:
                continue
            c = int(r[0])
            par = parent_of(names9.get(c, ""))
            if not par:
                continue
            cx, cy, w, h = map(float, r[1:5])
            boxes.append((par, [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]))
        gt[stem] = boxes
    return gt


def predict_parent(model, gt):
    """在 desk9 val 图上跑 model，细类聚合到 cup/bottle 父类，返回 {stem: [(parent, conf, xyxy)]}。"""
    out = {}
    for stem in gt:
        imgp = _find_image(stem)
        if not imgp:
            out[stem] = []
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
            par = parent_of(model.names.get(cid, ""))
            if par:
                items.append((par, conf, [xy[0] / w, xy[1] / h, xy[2] / w, xy[3] / h]))
        out[stem] = items
    return out


def evaluate_parent(preds, gt):
    """父类(cup/bottle)级 P/R：贪心 IoU 匹配，同父类才算 TP。"""
    parents = ("cup", "bottle")
    stats = {p: {"tp": 0, "fp": 0, "fn": 0} for p in parents}
    for stem, gboxes in gt.items():
        pitems = preds.get(stem, [])
        matched = set()
        for par, gxy in gboxes:
            best = None
            for j, (pc, conf, pxy) in enumerate(pitems):
                if pc != par or j in matched:
                    continue
                v = iou(gxy, pxy)
                if v >= IOU and (best is None or v > best[0]):
                    best = (v, j)
            if best:
                matched.add(best[1])
                stats[par]["tp"] += 1
            else:
                stats[par]["fn"] += 1
        for j, (pc, conf, pxy) in enumerate(pitems):
            if j not in matched:
                stats[pc]["fp"] += 1
    per = {}
    for p in parents:
        s = stats[p]
        prec = s["tp"] / (s["tp"] + s["fp"]) if (s["tp"] + s["fp"]) else 0.0
        rec = s["tp"] / (s["tp"] + s["fn"]) if (s["tp"] + s["fn"]) else 0.0
        per[p] = {"precision": round(prec, 3), "recall": round(rec, 3),
                  "tp": s["tp"], "fp": s["fp"], "fn": s["fn"]}
    return per


def main():
    report = {
        "conf": CONF, "iou": IOU,
        "caveats": [
            "desk_fine 原生 val 97 图 / desk9 val 93 图（保留规则不同，非同一集合）",
            "数据集干净桌面偏置；含增强重复、无会话分组、可能泄漏",
            "cup/bottle 家族细类在 val 上 support 极小(can/waterpot/disposable_cup 等个位数)，每类 P/R 噪声大",
            "父类聚合对比在 desk9 val(93) 共同基准上进行，数字仅供相对比较",
            "desk_fine 原生 mAP 用 ultralytics 默认 conf(0.001) 计算，与 Phase 1 desk9 mAP50=0.848 方法一致可对比；23 类词表 mAP 天然低于 9 类（类更多、含长尾），比较应看每类而非总 mAP",
            "父类聚合(Part3)两模型均在 conf=0.25 下用 model.predict，与 Phase 1 eval_track1.json 的 finetuned_per_class 同口径",
        ],
    }

    if not os.path.exists(FINE_WEIGHTS):
        report["error"] = f"缺权重 {FINE_WEIGHTS}（desk_fine 训练未完成），Track1b 无法评测"
        os.makedirs(os.path.dirname(REPORT), exist_ok=True)
        with open(REPORT, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return

    fine = YOLO(FINE_WEIGHTS)
    overview, per_class, families = fine_native_val(fine)
    report["desk_fine_val_images"] = 97
    report["desk_fine_native"] = overview
    report["desk_fine_per_class"] = per_class
    report["family_differentiation"] = families

    # Part3 父类聚合对比（需 desk9 权重）
    if os.path.exists(DESK9_WEIGHTS):
        d9 = YOLO(DESK9_WEIGHTS)
        gt = load_parent_gt(d9.names)
        report["parent_agg_val_images"] = len(gt)
        report["parent_agg_desk9"] = evaluate_parent(predict_parent(d9, gt), gt)
        report["parent_agg_desk_fine"] = evaluate_parent(predict_parent(fine, gt), gt)
        d9r = report["parent_agg_desk9"]
        dfr = report["parent_agg_desk_fine"]
        report["parent_agg_delta"] = {
            p: {"precision": round(dfr[p]["precision"] - d9r[p]["precision"], 3),
                "recall": round(dfr[p]["recall"] - d9r[p]["recall"], 3)}
            for p in ("cup", "bottle")
        }
    else:
        report["parent_agg_desk9"] = None
        report["parent_agg_desk_fine"] = None
        report["parent_agg_note"] = "缺 desk9 权重，跳过父类聚合对比"

    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
