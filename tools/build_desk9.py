#!/usr/bin/env python3
"""把 YOLO-DeskDataset 标签归一化(int/float)并按 configs/category_map.yaml 重映射为 9 产品类。

- 不修改原始数据集；产物写到 data/desk9/{train,val}/{images,labels}。
- images 用符号链接指向原图，避免复制 ~1.3GB。
- 原始 80 类标签旁挂到 labels_raw/<stem>.txt 供 FR03 追溯。
- 重映射后无框的图直接丢弃(不参与训练)。
- 输出 data/desk9/data9.yaml 与每类统计。
"""
import glob
import os
from collections import Counter

from packages.vision.category_map import load_category_map, normalize_class_id

ROOT = "/mnt/d/AstraDesk/data/YOLO-DeskDataset/dataset"
OUT = "/mnt/d/AstraDesk/data/desk9"
MAP = "/mnt/d/AstraDesk/configs/category_map.yaml"


def main():
    cmap = load_category_map(MAP)
    d2p = cmap["dataset_to_product"]
    names = cmap["product_classes"]

    for split in ("train", "val"):
        src_lab = os.path.join(ROOT, split, "labels")
        src_img = os.path.join(ROOT, split, "images")
        dst_lab = os.path.join(OUT, split, "labels")
        dst_raw = os.path.join(OUT, split, "labels_raw")
        dst_img = os.path.join(OUT, split, "images")
        for d in (dst_lab, dst_raw, dst_img):
            os.makedirs(d, exist_ok=True)

        kept_img = dropped_img = kept_box = dropped_box = 0
        cls = Counter()
        for lp in sorted(glob.glob(os.path.join(src_lab, "*.txt"))):
            stem = os.path.splitext(os.path.basename(lp))[0]
            rows = [ln.split() for ln in open(lp, encoding="utf-8").read().strip().splitlines() if ln.strip()]
            new, raw = [], []
            for r in rows:
                if len(r) < 5:
                    continue
                cid = normalize_class_id(r[0])
                raw.append(" ".join(r))
                if cid in d2p:
                    p = d2p[cid]
                    new.append(f"{p} {r[1]} {r[2]} {r[3]} {r[4]}")
                    cls[p] += 1
                    kept_box += 1
                else:
                    dropped_box += 1
            imgp = None
            for ext in ("jpg", "jpeg", "png", "JPG", "JPEG", "PNG"):
                cand = os.path.join(src_img, stem + "." + ext)
                if os.path.exists(cand):
                    imgp = cand
                    break
            if imgp is None or not new:
                dropped_img += 1
                continue
            with open(os.path.join(dst_lab, stem + ".txt"), "w", encoding="utf-8") as f:
                f.write("\n".join(new) + "\n")
            with open(os.path.join(dst_raw, stem + ".txt"), "w", encoding="utf-8") as f:
                f.write("\n".join(raw) + "\n")
            link = os.path.join(dst_img, os.path.basename(imgp))
            if not os.path.lexists(link):
                os.symlink(imgp, link)
            kept_img += 1
        print(f"[{split}] kept_img={kept_img} dropped_img={dropped_img} kept_box={kept_box} dropped_box={dropped_box}")
        print(f"[{split}] per-class:", {names[k]: v for k, v in sorted(cls.items())})

    names_list = [names[i] for i in sorted(names)]
    with open(os.path.join(OUT, "data9.yaml"), "w", encoding="utf-8") as f:
        f.write(f"path: {OUT}\ntrain: train/images\nval: val/images\n\nnames:\n")
        for i in sorted(names):
            f.write(f"  {i}: {names[i]}\n")
    print("wrote", os.path.join(OUT, "data9.yaml"), "names=", names_list)


if __name__ == "__main__":
    main()
