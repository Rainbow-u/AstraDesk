"""YOLO-World 开放词表检测适配器（Phase 2：凌乱桌面召回补充）。

与微调检测器(detector.py)互补：微调模型覆盖 23 产品类(version 2)，开放词表用文本提示补捉
凌乱场景下的额外桌面物(归 other)与漏检产品类。缺权重/依赖抛 DetectorUnavailable，
不静默跳过（AGENTS.md 约定1）。
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import List, Tuple

from .category_map import load_category_map
from .detector import Detection, DetectionResult, DetectorUnavailable

_WORLD = None
_WORLD_KEY = None

# 产品词表索引与 other 兜底 id 由 category_map(version 2) 派生，保证单一事实来源、避免索引漂移。
_CMAP = load_category_map()
_PRODUCT_INDEX = {name: idx for idx, name in _CMAP["product_classes"].items()}  # 含 other->23
OTHER_NAME = "other"
OTHER_ID = _PRODUCT_INDEX[OTHER_NAME]

# 23 训练类英文提示词（与 version 2 产品词表对齐；细类用数据集英文原名，YOLO-World 文本可区分）
PRODUCT_PROMPTS = [
    "laptop", "monitor", "keyboard", "mouse", "mobile phone", "book", "pen",
    "cup", "thermos cup", "plastic cup", "disposable cup",
    "bottle", "plastic bottle", "squeeze bottle", "can", "waterpot",
    "cable", "charger", "tissue", "paper", "lamp", "headphones", "mouse pad",
]
# 候选池/常见桌面物，命中归 other（本轮未转正；凌乱桌面需要召回，FR04 人工补框）
EXTRA_PROMPTS = [
    "earphones", "tablet", "speaker", "pencil case", "phone holder", "document",
    "power bank", "sticky notes", "stapler", "backpack", "wallet", "glasses",
    "watch", "fan", "eraser", "gamepad", "box", "carton", "waste paper ball",
]

# 开放词表提示词 -> 产品类名（未列出者归 other）
_PROMPT_TO_PRODUCT = {
    "laptop": "laptop", "monitor": "monitor", "keyboard": "keyboard",
    "mouse": "mouse", "mobile phone": "mobile_phone", "book": "book", "pen": "pen",
    "cup": "cup", "thermos cup": "thermos_cup", "plastic cup": "plastic_cup",
    "disposable cup": "disposable_cup",
    "bottle": "bottle", "plastic bottle": "plastic_bottle", "squeeze bottle": "squeeze_bottle",
    "can": "can", "waterpot": "waterpot",
    "cable": "cable", "charger": "charger", "tissue": "tissue", "paper": "paper",
    "lamp": "lamp", "headphones": "headphones", "mouse pad": "mouse_pad",
}


def openvocab_to_product(name: str) -> Tuple[int, str]:
    """开放词表提示词名 -> (产品类索引, 产品类名)；未命中归 other。"""
    prod = _PROMPT_TO_PRODUCT.get((name or "").strip().lower())
    if prod is None:
        return OTHER_ID, OTHER_NAME
    return _PRODUCT_INDEX[prod], prod


def _load_world(weights_path: Path):
    global _WORLD, _WORLD_KEY
    key = str(weights_path)
    if _WORLD is not None and _WORLD_KEY == key:
        return _WORLD
    try:
        from ultralytics import YOLOWorld, settings
    except Exception as exc:  # pragma: no cover - 环境相关
        raise DetectorUnavailable(f"ultralytics YOLOWorld not importable: {exc}") from exc
    settings.update({"sync": False})
    if not weights_path.exists():
        raise DetectorUnavailable(f"open-vocab weights not found: {weights_path}")
    _WORLD = YOLOWorld(str(weights_path))
    _WORLD.set_classes(PRODUCT_PROMPTS + EXTRA_PROMPTS)
    _WORLD_KEY = key
    return _WORLD


def detect_open_vocab(image, weights_path: Path, device: str = "", conf: float = 0.15) -> DetectionResult:
    """开放词表检测，返回带 source=yolo-world 的原始提示词类别结果（映射在 fusion 层做）。"""
    model = _load_world(weights_path)
    w, h = image.size
    kwargs = {"verbose": False, "conf": conf}
    if device:
        kwargs["device"] = device
    t0 = time.perf_counter()
    preds = model.predict(image, **kwargs)
    elapsed = time.perf_counter() - t0
    dets: List[Detection] = []
    boxes = preds[0].boxes
    for i in range(len(boxes)):
        cid = int(boxes.cls[i])
        conf_i = float(boxes.conf[i])
        xy = boxes.xyxy[i].tolist()
        name = model.names.get(cid, str(cid))
        dets.append(Detection(class_id=cid, class_name=name, confidence=conf_i,
                              bbox_image=[xy[0] / w, xy[1] / h, xy[2] / w, xy[3] / h],
                              source="yolo-world"))
    return DetectionResult(
        model_name="yolo-world",
        model_version=Path(str(weights_path)).name,
        run_mode="real",
        elapsed_seconds=elapsed,
        detections=dets,
        image_width=w,
        image_height=h,
        device=device or "auto",
    )
