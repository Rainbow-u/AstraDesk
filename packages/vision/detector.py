"""桌面物体检测适配器。

坐标约定（PRD 5.2）：``bbox_image = [x1, y1, x2, y2]``，归一化 0-1，左上原点。

运行模式（AGENTS.md 约定1）：
- ``detect_real``：走本地 ultralytics YOLOv10；缺依赖/权重时抛 ``DetectorUnavailable``，
  **不静默回退 mock**。
- ``detect_mock``：确定性 Mock，仅用于无 GPU 的契约测试与 demo，model_name 显式标注 ``mock``。
- ``detect``：按 run_mode 分派的统一入口。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

_MODEL = None  # 进程内懒加载，避免 worker 每次调用重载
_MODEL_KEY: Optional[str] = None


class DetectorUnavailable(RuntimeError):
    """真实检测不可用（缺 ultralytics / 权重 / GPU）。real 模式据此报 MODEL_UNAVAILABLE。"""


@dataclass
class Detection:
    """单个检测结果。bbox_image 归一化 0-1。"""

    class_id: int
    class_name: str
    confidence: float
    bbox_image: List[float] = field(default_factory=list)
    source: str = ""  # 检测来源(yolov10:<权重stem> / yolo-world / manual / mock)，FR03 可追溯
    raw_class_name: str = ""  # 开放词表映射前的原始提示词名(如 lamp/speaker)；主检测与映射后同名为空。FR03 原始类可追溯


@dataclass
class DetectionResult:
    """一次检测的完整输出。"""

    model_name: str
    model_version: str
    run_mode: str
    elapsed_seconds: float
    detections: List[Detection] = field(default_factory=list)
    image_width: int = 0
    image_height: int = 0
    device: str = ""


def _load_model(weights_path: Path):
    """加载（并缓存）YOLO 模型。缺依赖或权重文件时抛 DetectorUnavailable。"""
    global _MODEL, _MODEL_KEY
    key = str(weights_path)
    if _MODEL is not None and _MODEL_KEY == key:
        return _MODEL
    try:
        from ultralytics import YOLO, settings
    except Exception as exc:  # pragma: no cover - 环境相关
        raise DetectorUnavailable(f"ultralytics not importable: {exc}") from exc
    settings.update({"sync": False})  # 关闭遥测/联网同步，避免触发被墙的网络请求
    if not weights_path.exists():
        raise DetectorUnavailable(f"weights not found: {weights_path}")
    _MODEL = YOLO(str(weights_path))
    _MODEL_KEY = key
    return _MODEL


def detect_real(image, weights_path: Path, device: str = "", conf: float = 0.25) -> DetectionResult:
    """对 PIL 图像做真实 YOLOv10 检测，返回归一化坐标结果。"""
    model = _load_model(weights_path)
    stem = Path(str(weights_path)).stem
    w, h = image.size
    predict_kwargs = {"verbose": False, "conf": conf}
    if device:
        predict_kwargs["device"] = device
    t0 = time.perf_counter()
    preds = model.predict(image, **predict_kwargs)
    elapsed = time.perf_counter() - t0

    used_device = device or str(getattr(preds[0].boxes, "device", "") or "auto")
    detections: List[Detection] = []
    boxes = preds[0].boxes
    for i in range(len(boxes)):
        xyxy = boxes.xyxy[i].tolist()
        conf_i = float(boxes.conf[i])
        cid = int(boxes.cls[i])
        name = model.names.get(cid, str(cid))
        x1, y1, x2, y2 = xyxy[0] / w, xyxy[1] / h, xyxy[2] / w, xyxy[3] / h
        detections.append(
            Detection(class_id=cid, class_name=name, confidence=conf_i,
                      bbox_image=[x1, y1, x2, y2], source=f"yolov10:{stem}")
        )
    return DetectionResult(
        model_name=stem,
        model_version=Path(str(weights_path)).name,
        run_mode="real",
        elapsed_seconds=elapsed,
        detections=detections,
        image_width=w,
        image_height=h,
        device=used_device,
    )


def detect_mock(image) -> DetectionResult:
    """无 GPU 的确定性 Mock，仅用于契约测试与 demo。显式标注 mock。

    类别采用产品类词表（0 laptop / 3 mouse），与 detection_result 契约枚举一致。
    """
    w, h = image.size
    return DetectionResult(
        model_name="mock-detector",
        model_version="mock-0.1",
        run_mode="mock",
        elapsed_seconds=0.0,
        detections=[
            Detection(class_id=0, class_name="laptop", confidence=0.5,
                      bbox_image=[0.25, 0.25, 0.75, 0.75], source="mock"),
            Detection(class_id=3, class_name="mouse", confidence=0.4,
                      bbox_image=[0.55, 0.6, 0.62, 0.68], source="mock"),
        ],
        image_width=w,
        image_height=h,
        device="mock",
    )


def detect(image, run_mode: str, weights_path: Path, device: str = "", conf: float = 0.25) -> DetectionResult:
    """按运行模式分派的统一检测入口。"""
    if run_mode == "real":
        return detect_real(image, weights_path=weights_path, device=device, conf=conf)
    return detect_mock(image)
