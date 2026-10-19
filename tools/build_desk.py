#!/usr/bin/env python3
"""把 YOLO-DeskDataset 标签归一化(int/float)并按 configs/category_map.yaml 重映射为产品训练类。

build_desk9.py 的泛化版：类数不再写死，由 category_map 驱动（version 2 = 23 训练类 + other 兜底）。

- 不修改原始数据集；产物写到 data/desk_fine/{train,val}/{images,labels,labels_raw}。
- images 用符号链接指向原图，避免复制 ~1.3GB。
- 原始 80 类标签旁挂到 labels_raw/<stem>.txt 供 FR03 追溯。
- 重映射后无框的图直接丢弃(不参与训练)。
- 训练类 = dataset_to_product 的目标索引集合(0..nc-1 连续)；名为 other 的兜底类不参训、不写入 data yaml。
- 输出 data/desk_fine/data_fine.yaml 与每类框数统计(核对长尾)。
"""
import glob
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from packages.vision.category_map import load_category_map, normalize_class_id  # noqa: E402

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.environ.get("ASTRADESK_DESK_SRC", os.path.join(PROJECT_ROOT, "data", "YOLO-DeskDataset", "dataset"))
OUT = os.environ.get("ASTRADESK_DESK_OUT", os.path.join(PROJECT_ROOT, "data", "desk_fine"))
MAP = os.environ.get("ASTRADESK_DESK_MAP", os.path.join(PROJECT_ROOT, "configs", "category_map.yaml"))
DATA_YAML = os.environ.get("ASTRADESK_DESK_DATA_YAML", "data_fine.yaml")


def trained_names(names, d2p):
    """训练类索引 -> 名。排除 other 兜底类；校验目标索引 0..nc-1 连续（YOLO 要求）。"""
    trained = {i: n for i, n in names.items() if n != "other"}
    used = set(d2p.values())
    if used != set(trained):
        # 允许 other 无映射；但除 other 外，凡声明的训练类都应有数据来源
        missing = set(trained) - used
        extra = used - set(trained)
        raise SystemExit(f"category_map 不一致: 声明训练类缺数据源={sorted(missing)} 数据源含非训练类={sorted(extra)}")
    idxs = sorted(trained)
    if idxs != list(range(len(idxs))):
        raise SystemExit(f"训练类索引必须 0..nc-1 连续，实得 {idxs}")
    return trained


def main():
    cmap = load_category_map(MAP)
    d2p = cmap["dataset_to_product"]
    names = cmap["product_classes"]
    trained = trained_names(names, d2p)
    nc = len(trained)
    print(f"category_map version={cmap['version']} nc(训练类)={nc} other_index={[i for i,n in names.items() if n=='other']}")

    total_cls = Counter()
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
        total_cls.update(cls)
        print(f"[{split}] kept_img={kept_img} dropped_img={dropped_img} kept_box={kept_box} dropped_box={dropped_box}")
        print(f"[{split}] per-class:", {trained[k]: v for k, v in sorted(cls.items())})

    names_list = [trained[i] for i in sorted(trained)]
    with open(os.path.join(OUT, DATA_YAML), "w", encoding="utf-8") as f:
        f.write(f"path: {OUT}\ntrain: train/images\nval: val/images\n\nnames:\n")
        for i in sorted(trained):
            f.write(f"  {i}: {trained[i]}\n")
    print("wrote", os.path.join(OUT, DATA_YAML), "nc=", nc, "names=", names_list)
    # 长尾核查：每类合计框数升序
    print("[all] per-class boxes(train+val) 升序:",
          sorted(((total_cls[i], trained[i]) for i in sorted(trained))))


if __name__ == "__main__":
    main()
