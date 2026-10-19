"""确定性物体属性提取（Phase 4 阶段 B：颜色 + 几何，免训练、离线、可复现）。

两类**确定性**属性（PRD 5.1 属性词表；红线1/7 无真实测量不编数字）：

- **颜色**（需关联原图像素）：把 ``bbox_image``（原图归一化框）反归一化到像素，取框内
  主色（RGB 量化直方图峰值 bin 的代表色），映射中文基本色名 + rgb/hsv。**无原图时返回
  ``unknown``，绝不编造**（显式 objects 路径未关联 image asset 即属此情形）。
- **几何**（仅需 ``bbox_desk``）：``aspect_ratio``、``orientation``（横/方/竖）、
  ``size_class``（小/中/大，按占桌面面积比分档）。与 scene_facts 同源坐标约定
  （``bbox_desk ∈ [0,1]^2``，桌面归一化相对量，非物理量）。

**语义属性**（材质/开合/空满/精确朝向）不在本模块——HF 数据无标注、VL 凭据未到位，
由 ``vl_interpreter`` 预留接口在 B 阶段之后填充；当前恒为 ``blocked``（全 null），
见 ``scene_facts.schema.json`` 的 ``attributes.semantic`` 块。

确定性保证：同图同框同结果（numpy 量化直方图 + stdlib ``colorsys``，无随机、无网络、
无模型）；直方图峰值 ties 由 ``np.unique`` 升序 + ``argmax`` 取首个最大决定，稳定可复现。
"""
from __future__ import annotations

import colorsys
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

ATTRIBUTES_VERSION = "1.0"

# 中文基本色名（12 种，PRD 5.1）；unknown 表示无原图不可测（不编造）。
COLOR_NAMES_ZH = ("黑", "白", "灰", "红", "橙", "黄", "绿", "青", "蓝", "紫", "棕", "粉")
UNKNOWN_COLOR = "unknown"

# 几何分档阈值（确定性启发式；桌面归一化相对量，非物理量）。
ORIENTATION_LANDSCAPE_MIN = 1.2       # aspect_ratio ≥ 1.2 → landscape(横)
ORIENTATION_PORTRAIT_MAX = 1.0 / 1.2  # aspect_ratio ≤ 0.833 → portrait(竖)；其间 → square(方)
SIZE_SMALL_MAX = 0.02                 # 占桌面面积比 < 2% → small
SIZE_MEDIUM_MAX = 0.10                # < 10% → medium；≥ 10% → large

# 颜色命名阈值（HSV：h∈[0,360)、s∈[0,1]、v∈[0,1]）。
_V_BLACK = 0.16        # v 低于此 → 黑
_S_ACHROMATIC = 0.12   # s 低于此 → 无彩色（白/灰）
_V_WHITE = 0.85        # 无彩色且 v 高于此 → 白，否则灰
_V_BROWN = 0.55        # 暖色相(橙黄)且 v 低于此 → 棕
_V_PINK = 0.78         # 红/品红相、v 高于此且 s 较低 → 粉
_S_PINK = 0.50
_QUANT_SHIFT = 4       # RGB 量化右移位数（每通道 16 级 → 4096 bin）

# 语义属性预留块（B 阶段 blocked；由 vl_interpreter 在凭据到位后填充，H01 不改事实清单）。
SEMANTIC_STATUS_BLOCKED = "blocked"
SEMANTIC_STATUS_AVAILABLE = "available"
_SEMANTIC_FIELDS = ("material", "open_state", "fill_level", "precise_orientation")


def unknown_color() -> Dict:
    """无原图/不可测时的颜色（诚实标注 unknown，不编造 rgb/hsv）。"""
    return {"name": UNKNOWN_COLOR, "rgb": None, "hsv": None}


def blocked_semantic() -> Dict:
    """语义属性预留块：当前恒 blocked（全 null），待 VL 凭据到位后填充。"""
    sem: Dict[str, Optional[str]] = {"status": SEMANTIC_STATUS_BLOCKED}
    for f in _SEMANTIC_FIELDS:
        sem[f] = None
    return sem


def _clamp_int(v: float, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(v)))


def _rgb_to_hsv(r: int, g: int, b: int) -> Tuple[float, float, float]:
    """RGB(0-255) → HSV(h∈[0,360)、s∈[0,1]、v∈[0,1])。stdlib colorsys，确定性。"""
    h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    return h * 360.0, s, v


def color_name_zh(h: float, s: float, v: float) -> str:
    """HSV → 中文基本色名（确定性规则分档；h∈[0,360)、s,v∈[0,1]）。

    顺序：先判黑（低明度）→ 无彩色（低饱和：白/灰）→ 棕（暖色相偏暗）→
    粉（红/品红偏亮低饱和）→ 其余按色相环分带（红橙黄绿青蓝紫，品红归粉）。
    """
    if v < _V_BLACK:
        return "黑"
    if s < _S_ACHROMATIC:
        return "白" if v > _V_WHITE else "灰"
    if v < _V_BROWN and 12.0 <= h < 60.0:
        return "棕"
    if v > _V_PINK and s < _S_PINK and (h < 20.0 or h >= 320.0):
        return "粉"
    if h < 12.0 or h >= 345.0:
        return "红"
    if h < 45.0:
        return "橙"
    if h < 75.0:
        return "黄"
    if h < 165.0:
        return "绿"
    if h < 195.0:
        return "青"
    if h < 255.0:
        return "蓝"
    if h < 290.0:
        return "紫"
    return "粉"  # 290–345 品红


def _dominant_rgb(arr: np.ndarray) -> Tuple[int, int, int]:
    """量化直方图峰值 bin 内像素的平均 RGB（确定性）。

    每通道右移 4 位量化到 16 级 → 4096 bin；取像素数最多的 bin（ties 取最小 key，
    因 np.unique 升序 + argmax 取首个最大），再对该 bin 内原始 RGB 取均值作代表色。
    """
    q = arr.astype(np.int32) >> _QUANT_SHIFT          # (N,3)，每通道 0..15
    key = (q[:, 0] << 8) | (q[:, 1] << 4) | q[:, 2]   # 0..4095 唯一编码
    vals, counts = np.unique(key, return_counts=True)
    top = vals[int(np.argmax(counts))]
    mean = arr[key == top].mean(axis=0)
    return int(round(float(mean[0]))), int(round(float(mean[1]))), int(round(float(mean[2])))


def extract_color(image, bbox_image: Optional[Sequence[float]]) -> Dict:
    """从原图 ``bbox_image``（原图归一化 [x1,y1,x2,y2]）区域取主色。

    返回 ``{name, rgb:[r,g,b]|None, hsv:[h,s,v]|None}``；``name`` 为中文基本色名或
    ``"unknown"``。image 为 None / 无有效尺寸 / 框退化 / 无像素 → unknown（不编造）。
    """
    if image is None or bbox_image is None:
        return unknown_color()
    size = getattr(image, "size", None)
    if not size:
        return unknown_color()
    w, h = size
    if w <= 0 or h <= 0:
        return unknown_color()
    if len(bbox_image) != 4:
        return unknown_color()
    x1, y1, x2, y2 = (float(v) for v in bbox_image)
    px1 = _clamp_int(round(x1 * w), 0, w - 1)
    py1 = _clamp_int(round(y1 * h), 0, h - 1)
    px2 = _clamp_int(round(x2 * w), 0, w)
    py2 = _clamp_int(round(y2 * h), 0, h)
    if px2 <= px1 or py2 <= py1:
        return unknown_color()
    region = image.crop((px1, py1, px2, py2)).convert("RGB")
    arr = np.asarray(region).reshape(-1, 3)
    if arr.shape[0] == 0:
        return unknown_color()
    r, g, b = _dominant_rgb(arr)
    hh, ss, vv = _rgb_to_hsv(r, g, b)
    return {
        "name": color_name_zh(hh, ss, vv),
        "rgb": [r, g, b],
        "hsv": [round(hh, 1), round(ss, 3), round(vv, 3)],
    }


def geometry_attrs(bbox_desk: Sequence[float]) -> Dict:
    """从 ``bbox_desk``（桌面归一化 [x1,y1,x2,y2]）派生几何属性（确定性）。

    返回 ``{aspect_ratio, orientation, size_class}``：
    - ``aspect_ratio`` = 宽/高（桌面归一化单位，>1 偏横）；
    - ``orientation`` = landscape(横)/square(方)/portrait(竖) 按宽高比分档；
    - ``size_class`` = small/medium/large 按占桌面面积比 (w*h) 分档。
    """
    if len(bbox_desk) != 4:
        raise ValueError(f"bbox_desk needs 4 floats, got {len(bbox_desk)}")
    x1, y1, x2, y2 = (float(v) for v in bbox_desk)
    w = max(0.0, x2 - x1)
    h = max(0.0, y2 - y1)
    aspect = round(w / h, 4) if h > 0 else 0.0
    if aspect >= ORIENTATION_LANDSCAPE_MIN:
        orientation = "landscape"
    elif aspect <= ORIENTATION_PORTRAIT_MAX:
        orientation = "portrait"
    else:
        orientation = "square"
    area = w * h
    if area < SIZE_SMALL_MAX:
        size_class = "small"
    elif area < SIZE_MEDIUM_MAX:
        size_class = "medium"
    else:
        size_class = "large"
    return {"aspect_ratio": aspect, "orientation": orientation, "size_class": size_class}


def object_attributes(image, bbox_image: Optional[Sequence[float]],
                      bbox_desk: Sequence[float]) -> Dict:
    """组合物体属性：颜色（需原图，缺则 unknown）+ 几何（需 bbox_desk）+ 语义预留（blocked）。

    返回结构与 ``scene_facts.schema.json`` 的 ``object.attributes`` 对齐：
    ``{color, aspect_ratio, orientation, size_class, semantic}``。确定性、离线、可复现。
    """
    geo = geometry_attrs(bbox_desk)
    return {
        "color": extract_color(image, bbox_image),
        "aspect_ratio": geo["aspect_ratio"],
        "orientation": geo["orientation"],
        "size_class": geo["size_class"],
        "semantic": blocked_semantic(),
    }
