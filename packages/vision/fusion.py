"""检测融合：微调框(主) + 开放词表框(补)，类无关 NMS 去重（Phase 2）。

规则：
- 主检测(微调 YOLOv10)全部保留，source 不变。
- 开放词表检测先映射到产品类(未命中归 other)，再与"已保留框"做类无关 IoU 去重：
  与任一已保留框 IoU>=thr 则抑制(信任主检测)；否则保留并打 source=yolo-world。
- 开放词表彼此之间也做 NMS 去重。
每框带 source + 原始类 + conf，满足 FR03 可追溯。
"""
from __future__ import annotations

from dataclasses import replace
from typing import Callable, List

from .detector import Detection
from .open_vocab import openvocab_to_product


def iou(a: List[float], b: List[float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    ua = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - inter
    return inter / ua if ua > 0 else 0.0


def fuse(primary: List[Detection], secondary: List[Detection],
         iou_thr: float = 0.5,
         mapper: Callable[[str], tuple] = openvocab_to_product) -> List[Detection]:
    """融合主/补检测。secondary 的 class_name 为开放词表原始提示词名，经 mapper 映射到产品类。"""
    kept: List[Detection] = list(primary)
    kept_boxes = [d.bbox_image for d in kept]
    # 补检测按置信度降序，先做彼此 NMS 再与主框去重
    for det in sorted(secondary, key=lambda d: d.confidence, reverse=True):
        if any(iou(det.bbox_image, kb) >= iou_thr for kb in kept_boxes):
            continue  # 与已保留框重叠，信任主检测，抑制
        pidx, pname = mapper(det.class_name)
        # 保留开放词表原始提示词名(FR03 原始类可追溯)：映射为 other 后仍可知“原本是什么”
        kept.append(replace(det, class_id=pidx, class_name=pname,
                            raw_class_name=det.class_name))
        kept_boxes.append(det.bbox_image)
    return kept
