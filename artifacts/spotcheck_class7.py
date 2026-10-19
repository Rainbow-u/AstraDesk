#!/usr/bin/env python3
"""抽查 YOLO-DeskDataset 中 class_id=7 (computer) 的实例，裁剪保存到 artifacts/_tmp_class7 供目视判定是否并入 monitor。只读数据集，不改原文件。"""
import glob
import os

from PIL import Image

ROOT = "/mnt/d/AstraDesk/data/YOLO-DeskDataset/dataset"
OUT = "/mnt/d/AstraDesk/artifacts/_tmp_class7"
os.makedirs(OUT, exist_ok=True)

labels = sorted(glob.glob(os.path.join(ROOT, "train/labels", "*.txt")))
found = 0
for lp in labels:
    if found >= 6:
        break
    with open(lp) as f:
        rows = [ln.split() for ln in f.read().strip().splitlines() if ln.strip()]
    hits = [r for r in rows if len(r) >= 5 and int(float(r[0])) == 7]
    if not hits:
        continue
    stem = os.path.splitext(os.path.basename(lp))[0]
    imgp = None
    for ext in ("jpg", "jpeg", "png", "JPG", "JPEG", "PNG"):
        cand = os.path.join(ROOT, "train/images", stem + "." + ext)
        if os.path.exists(cand):
            imgp = cand
            break
    if not imgp:
        continue
    im = Image.open(imgp).convert("RGB")
    W, H = im.size
    for i, r in enumerate(hits):
        cx, cy, w, h = map(float, r[1:5])
        x1 = int((cx - w / 2) * W)
        y1 = int((cy - h / 2) * H)
        x2 = int((cx + w / 2) * W)
        y2 = int((cy + h / 2) * H)
        m = 24
        crop = im.crop((max(0, x1 - m), max(0, y1 - m), min(W, x2 + m), min(H, y2 + m)))
        p = os.path.join(OUT, f"class7_{found:02d}_{i}.jpg")
        crop.save(p)
        print(p, crop.size, "src=", os.path.basename(imgp))
        found += 1
        if found >= 6:
            break
print("done crops=", found)
