"""类别映射与标签归一化（configs/category_map.yaml 的加载与纯函数）。

供 build_desk9(数据修复)、detector/fusion(推理映射)、测试共用，保证单一事实来源。
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import yaml

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "category_map.yaml"


class CategoryMapError(ValueError):
    """类别映射配置非法。"""


def normalize_class_id(token) -> int:
    """把标签 class_id 归一化为 int。数据集存在 '8' 与 '8.0' 混写，统一 int(float(x))。"""
    return int(float(token))


def load_category_map(path=None) -> dict:
    """加载版本化映射，返回 {version, product_classes:{idx:name}, dataset_to_product:{cid:idx}, notes}。"""
    p = Path(path) if path else _CONFIG_PATH
    cfg = yaml.safe_load(p.read_text(encoding="utf-8"))
    names = {int(k): str(v) for k, v in cfg["product_classes"].items()}
    d2p = {int(k): int(v) for k, v in cfg["dataset_to_product"].items()}
    # 一致性校验：映射目标必须是已声明的产品类索引
    for cid, pidx in d2p.items():
        if pidx not in names:
            raise CategoryMapError(f"dataset class {cid} maps to unknown product index {pidx}")
    return {
        "version": cfg.get("version"),
        "product_classes": names,
        "dataset_to_product": d2p,
        "notes": cfg.get("notes", []),
    }


def product_names(cmap: dict) -> List[str]:
    """按索引顺序返回产品类名列表。"""
    return [cmap["product_classes"][i] for i in sorted(cmap["product_classes"])]


def dataset_to_product(cmap: dict, cid: int):
    """数据集 class_id -> 产品类索引；未命中返回 None(归 other，不参训)。"""
    return cmap["dataset_to_product"].get(int(cid))
