"""确定性场景事实计算（Phase 3 facts-first NL 的单一事实来源）。

输入 = 确认后的检测（object_id / class / bbox_desk）+ 靠用户侧 + 偏好；
输出结构化 ``SceneFacts``。所有量都是桌面归一化坐标（bbox_desk ∈ [0,1]^2）下的
**确定性几何计算**：离线、可复现、可测试，不依赖任何模型或随机性。

诚实边界（PRD 5.2）：近俯拍图像空间，未经相机标定 → 不给厘米距离、不推断真实重心/
支撑/碰撞。这里的“距离/面积”都是桌面归一化坐标下的相对量，仅作布局启发式。

H01：本模块产出的事实清单是单一事实来源，下游（模板/VL）只能引用其中已有的
object_id 与数值，不得改写。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .object_attributes import object_attributes

SCENE_FACTS_VERSION = "1.0"

GRID_N_DEFAULT = 20            # 5% 网格（PRD 6.3 候选分辨率一致）
H07_THRESHOLD_DEFAULT = 0.04   # PRD 6.1 H07：杯瓶与电子设备桌面坐标最短距离阈值
ALIGN_NORM = 1.0 / 6.0         # 对齐偏差归一化尺度（半个三分带）
CLUSTER_DIST = 0.20            # 同类聚类的单链接中心距阈值（桌面对角归一前）

VALID_USER_SIDES = ("bottom", "top", "left", "right")
VALID_HANDEDNESS = ("left", "right")
VALID_MODES = ("study", "office", "minimal")

# 功能组（PRD 6.2 同类集中/对齐按功能组计算）——version 2 词表(24 类)。
# electronics 含转正的电子/工作站配件(mouse_pad/cable/charger/headphones/lamp)；
# writing 含转正的 paper；drinkware 为杯瓶细分全集；tissue 不属任一组 -> 归 other 组。
FUNCTIONAL_GROUPS: Dict[str, Tuple[str, ...]] = {
    "electronics": ("laptop", "monitor", "keyboard", "mouse", "mouse_pad",
                    "mobile_phone", "headphones", "charger", "cable", "lamp"),
    "writing": ("book", "pen", "paper"),
    "drinkware": ("cup", "thermos_cup", "plastic_cup", "disposable_cup",
                  "bottle", "plastic_bottle", "squeeze_bottle", "can", "waterpot"),
}
OTHER_GROUP = "other"
# H07：杯瓶(液体容器) vs 电子设备(怕洒溅)。mouse_pad/tissue 非电子风险物，不计入 ELECTRONICS。
DRINKWARE = frozenset(FUNCTIONAL_GROUPS["drinkware"])
ELECTRONICS = frozenset({"laptop", "monitor", "keyboard", "mouse", "mobile_phone",
                         "headphones", "charger", "cable", "lamp"})
# 产品类词表（与 configs/category_map.yaml version 2、detection_result 契约一致；
# 顺序即训练类索引 0-23，索引 23=other 兜底）。一致性由 test_scene_facts 校验。
PRODUCT_CLASSES = ("laptop", "monitor", "keyboard", "mouse", "mobile_phone", "book", "pen",
                   "cup", "thermos_cup", "plastic_cup", "disposable_cup",
                   "bottle", "plastic_bottle", "squeeze_bottle", "can", "waterpot",
                   "cable", "charger", "tissue", "paper", "lamp", "headphones", "mouse_pad",
                   "other")


class SceneFactsError(ValueError):
    """输入非法（object_id 重复/空、bbox 越界、user_side 非法等）。"""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class SceneObject:
    """确认后的单个物品（桌面归一化坐标）。"""

    object_id: str
    class_name: str
    bbox_desk: List[float]          # [x1,y1,x2,y2] ⊂ [0,1]
    class_id: int = -1
    fixed: bool = False             # 固定不动（FR04/PRD 6.1 H03）
    high_frequency: bool = False    # 经常使用（FR04，用于取用便利）
    source: str = ""                # 检测来源，透传以便追溯（FR03）
    # 原图归一化框（颜色属性反归一化取像素用）；缺省 None → 颜色 unknown（不编造）。
    bbox_image: Optional[List[float]] = None


# ---------------------------------------------------------------- 几何基元

def _center(b: Sequence[float]) -> Tuple[float, float]:
    return ((b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0)


def _area(b: Sequence[float]) -> float:
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def _dist(p: Tuple[float, float], q: Tuple[float, float]) -> float:
    return math.hypot(p[0] - q[0], p[1] - q[1])


def rect_gap(a: Sequence[float], b: Sequence[float]) -> float:
    """两轴对齐矩形的最短欧氏距离；重叠时为 0（PRD 6.1 H07 用的“矩形最短距离”）。"""
    dx = max(0.0, max(a[0], b[0]) - min(a[2], b[2]))
    dy = max(0.0, max(a[1], b[1]) - min(a[3], b[3]))
    return math.hypot(dx, dy)


def _clamp01(x: float) -> float:
    return min(1.0, max(0.0, x))


def _band3(t: float) -> int:
    """把 [0,1] 三等分：0=近/左, 1=中, 2=远/右。"""
    if t < 1.0 / 3.0:
        return 0
    if t < 2.0 / 3.0:
        return 1
    return 2


# ---------------------------------------------------------------- 分区（靠用户侧）

def depth_from_user(cx: float, cy: float, user_side: str) -> float:
    """中心到“靠用户侧”边缘的归一化深度 t∈[0,1]（0=最靠近用户）。"""
    if user_side == "bottom":
        return 1.0 - cy
    if user_side == "top":
        return cy
    if user_side == "left":
        return cx
    if user_side == "right":
        return 1.0 - cx
    raise SceneFactsError("SCHEMA_INVALID", f"invalid user_side: {user_side!r}")


def zone_of(cx: float, cy: float, user_side: str) -> Dict[str, str]:
    """分区：depth(near/mid/far) × lateral。

    lateral 轴随靠用户侧而变：bottom/top → 沿 x（left/center/right）；
    left/right → 沿 y（top/middle/bottom）。
    """
    depth_names = ("near", "mid", "far")
    t = depth_from_user(cx, cy, user_side)
    depth = depth_names[_band3(t)]
    if user_side in ("bottom", "top"):
        lateral_names = ("left", "center", "right")
        lateral = lateral_names[_band3(cx)]
        lateral_axis = "x"
    else:
        lateral_names = ("top", "middle", "bottom")
        lateral = lateral_names[_band3(cy)]
        lateral_axis = "y"
    return {"depth": depth, "lateral": lateral, "lateral_axis": lateral_axis}


# ---------------------------------------------------------------- 占用网格

def _occupancy_grid(objects: Sequence[SceneObject], n: int) -> List[List[int]]:
    """网格占用：单元格中心落入任一物品框即记为占用（分辨率 n×n，文档标注近似）。"""
    grid = [[0] * n for _ in range(n)]
    for o in objects:
        x1, y1, x2, y2 = o.bbox_desk
        for r in range(n):
            cy = (r + 0.5) / n
            if cy < y1 or cy > y2:
                continue
            for c in range(n):
                cx = (c + 0.5) / n
                if x1 <= cx <= x2 and y1 <= cy <= y2:
                    grid[r][c] = 1
    return grid


def _largest_empty_rect(free: List[List[int]]) -> Tuple[int, int, int, int, int]:
    """在 0/1 矩阵中求最大全 1 轴对齐矩形（直方图法）。

    返回 (area_cells, top_row, left_col, bottom_row_inclusive, right_col_inclusive)。
    空矩阵返回 (0,0,0,-1,-1)。
    """
    rows = len(free)
    if rows == 0:
        return (0, 0, 0, -1, -1)
    cols = len(free[0])
    heights = [0] * cols
    best = (0, 0, 0, -1, -1)
    for r in range(rows):
        for c in range(cols):
            heights[c] = heights[c] + 1 if free[r][c] else 0
        # 单调栈求当前行直方图最大矩形
        stack: List[int] = []
        for c in range(cols + 1):
            h = heights[c] if c < cols else 0
            start = c
            while stack and stack[-1][1] >= h:
                sc, sh = stack.pop()
                width = c - sc
                area = sh * width
                if area > best[0]:
                    best = (area, r - sh + 1, sc, r, c - 1)
                start = sc
            stack.append((start, h))
    return best


def _work_region_mask(n: int, user_side: str) -> List[List[int]]:
    """“桌面中间偏近用户”工作区（PRD 6.2 连续工作区定义域）：lateral 中带 × depth 近-中。"""
    mask = [[0] * n for _ in range(n)]
    lo, hi = n // 3, (2 * n) // 3  # 中带 [1/3,2/3)
    for r in range(n):
        cy = (r + 0.5) / n
        for c in range(n):
            cx = (c + 0.5) / n
            if user_side in ("bottom", "top"):
                lat_ok = lo <= c < hi
                t = depth_from_user(cx, cy, user_side)
            else:
                lat_ok = lo <= r < hi
                t = depth_from_user(cx, cy, user_side)
            mask[r][c] = 1 if (lat_ok and t < 2.0 / 3.0) else 0
    return mask


# ---------------------------------------------------------------- 对齐

_REF_LINES = (0.0, 1.0 / 3.0, 2.0 / 3.0, 1.0)


def _min_edge_dev(b: Sequence[float]) -> List[float]:
    """四条边到最近参考线的偏差（x1,x2 对 x 参考线；y1,y2 对 y 参考线）。"""
    devs = []
    for v in (b[0], b[2]):
        devs.append(min(abs(v - rl) for rl in _REF_LINES))
    for v in (b[1], b[3]):
        devs.append(min(abs(v - rl) for rl in _REF_LINES))
    return devs


# ---------------------------------------------------------------- 聚类

def _cluster_by_class(objects: Sequence[SceneObject]) -> List[Dict]:
    """按类 + 邻近（单链接，中心距 ≤ CLUSTER_DIST）聚类，用于“N 个同类集中在某区”描述。"""
    clusters: List[Dict] = []
    by_class: Dict[str, List[SceneObject]] = {}
    for o in objects:
        by_class.setdefault(o.class_name, []).append(o)
    for name, items in by_class.items():
        used = [False] * len(items)
        for i in range(len(items)):
            if used[i]:
                continue
            group = [items[i]]
            used[i] = True
            changed = True
            while changed:
                changed = False
                for j in range(len(items)):
                    if used[j]:
                        continue
                    cj = _center(items[j].bbox_desk)
                    if any(_dist(cj, _center(g.bbox_desk)) <= CLUSTER_DIST for g in group):
                        group.append(items[j])
                        used[j] = True
                        changed = True
            centroid = [
                sum(_center(g.bbox_desk)[0] for g in group) / len(group),
                sum(_center(g.bbox_desk)[1] for g in group) / len(group),
            ]
            clusters.append({
                "class_name": name,
                "count": len(group),
                "object_ids": [g.object_id for g in group],
                "centroid": [round(centroid[0], 4), round(centroid[1], 4)],
            })
    clusters.sort(key=lambda c: (-c["count"], c["class_name"]))
    return clusters


def _group_of(class_name: str) -> str:
    for g, members in FUNCTIONAL_GROUPS.items():
        if class_name in members:
            return g
    return OTHER_GROUP


# ---------------------------------------------------------------- 主计算

def compute_scene_facts(
    objects: Sequence[SceneObject],
    user_side: str = "bottom",
    handedness: str = "right",
    mode: str = "office",
    grid_n: int = GRID_N_DEFAULT,
    h07_threshold: float = H07_THRESHOLD_DEFAULT,
    image=None,
) -> Dict:
    """确定性计算场景事实，返回可过 scene_facts.schema.json 的 dict。

    非法输入抛 SceneFactsError（不静默修正）。

    每个物品附 ``attributes``（Phase 4 阶段 B）：几何（aspect_ratio/orientation/size_class，
    恒可由 bbox_desk 确定派生）+ 颜色（需传入原图 ``image`` 且物品带 ``bbox_image``，
    否则 color.name=unknown，不编造）+ 语义预留（恒 blocked）。同图同框同结果，确定可复现。
    """
    if user_side not in VALID_USER_SIDES:
        raise SceneFactsError("SCHEMA_INVALID", f"user_side must be one of {VALID_USER_SIDES}")
    if handedness not in VALID_HANDEDNESS:
        raise SceneFactsError("SCHEMA_INVALID", f"handedness must be one of {VALID_HANDEDNESS}")
    if mode not in VALID_MODES:
        raise SceneFactsError("SCHEMA_INVALID", f"mode must be one of {VALID_MODES}")
    if grid_n < 4:
        raise SceneFactsError("SCHEMA_INVALID", f"grid_n too small: {grid_n}")

    seen = set()
    norm_objs: List[SceneObject] = []
    for o in objects:
        if not o.object_id:
            raise SceneFactsError("SCHEMA_INVALID", "object_id must be non-empty")
        if o.object_id in seen:
            raise SceneFactsError("SCHEMA_INVALID", f"duplicate object_id: {o.object_id}")
        seen.add(o.object_id)
        b = o.bbox_desk
        if len(b) != 4:
            raise SceneFactsError("SCHEMA_INVALID", f"{o.object_id}: bbox_desk needs 4 floats")
        x1, y1, x2, y2 = (float(v) for v in b)
        if not (0.0 <= x1 < x2 <= 1.0 and 0.0 <= y1 < y2 <= 1.0):
            raise SceneFactsError(
                "SCHEMA_INVALID",
                f"{o.object_id}: bbox_desk out of [0,1] or degenerate: {b}")
        if o.class_name not in PRODUCT_CLASSES:
            raise SceneFactsError("SCHEMA_INVALID", f"{o.object_id}: unknown class {o.class_name!r}")
        norm_objs.append(SceneObject(o.object_id, o.class_name, [x1, y1, x2, y2],
                                     o.class_id, o.fixed, o.high_frequency, o.source,
                                     list(o.bbox_image) if o.bbox_image is not None else None))

    n = grid_n
    total_cells = n * n
    grid = _occupancy_grid(norm_objs, n)
    occupied = sum(sum(row) for row in grid)
    occupied_ratio = occupied / total_cells
    free_ratio = 1.0 - occupied_ratio

    # 连续工作区：工作区域内的最大空矩形 / 工作区域面积
    mask = _work_region_mask(n, user_side)
    mask_cells = sum(sum(row) for row in mask)
    free_in_work = [[1 if (mask[r][c] and not grid[r][c]) else 0 for c in range(n)] for r in range(n)]
    area, tr, lc, br, rc = _largest_empty_rect(free_in_work)
    if mask_cells > 0 and area > 0:
        cw_ratio = area / mask_cells
        cw_rect = [round(lc / n, 4), round(tr / n, 4), round((rc + 1) / n, 4), round((br + 1) / n, 4)]
    else:
        cw_ratio = 0.0
        cw_rect = None

    # 对齐：所有物品四边到参考线的平均偏差
    all_dev: List[float] = []
    for o in norm_objs:
        all_dev.extend(_min_edge_dev(o.bbox_desk))
    mean_edge_dev = (sum(all_dev) / len(all_dev)) if all_dev else 0.0
    alignment_score = _clamp01(1.0 - mean_edge_dev / ALIGN_NORM) if all_dev else 1.0

    # 同类集中：按功能组，组内 ≥2 物品才算（单实例不惩罚）
    diag = math.sqrt(2.0)
    group_entries: List[Dict] = []
    by_group: Dict[str, List[SceneObject]] = {}
    for o in norm_objs:
        by_group.setdefault(_group_of(o.class_name), []).append(o)
    multi_scores: List[float] = []
    for gname in ("electronics", "writing", "drinkware", OTHER_GROUP):
        members = by_group.get(gname, [])
        if not members:
            continue
        centers = [_center(o.bbox_desk) for o in members]
        if len(members) >= 2:
            pairs = [(_dist(centers[i], centers[j]))
                     for i in range(len(members)) for j in range(i + 1, len(members))]
            avg_pair = sum(pairs) / len(pairs)
            score = _clamp01(1.0 - avg_pair / diag)
            multi_scores.append(score)
        else:
            avg_pair = None
            score = None  # 单实例不产生惩罚
        group_entries.append({
            "group": gname,
            "count": len(members),
            "avg_pairwise_distance": round(avg_pair, 4) if avg_pair is not None else None,
            "grouping_score": round(score, 4) if score is not None else None,
            "object_ids": [o.object_id for o in members],
        })
    grouping_score = round(sum(multi_scores) / len(multi_scores), 4) if multi_scores else None

    # 取用便利：高频物品中心到用户区锚点的距离（桌面对角归一）
    user_anchor = _user_anchor(user_side, handedness)
    accessibility: List[Dict] = []
    for o in norm_objs:
        if not o.high_frequency:
            continue
        d = _dist(_center(o.bbox_desk), user_anchor) / diag
        accessibility.append({
            "object_id": o.object_id, "class_name": o.class_name,
            "distance_to_user_region": round(d, 4),
        })
    accessibility.sort(key=lambda a: a["distance_to_user_region"])
    accessibility_score = (round(_clamp01(1.0 - sum(a["distance_to_user_region"] for a in accessibility)
                                          / len(accessibility)), 4) if accessibility else None)

    # H07：杯瓶与电子设备最短距离
    drinks = [o for o in norm_objs if o.class_name in DRINKWARE]
    elecs = [o for o in norm_objs if o.class_name in ELECTRONICS]
    if drinks and elecs:
        best = min(((rect_gap(d.bbox_desk, e.bbox_desk), d, e) for d in drinks for e in elecs), key=lambda x: x[0])
        gap, d_obj, e_obj = best[0], best[1], best[2]
        h07 = {
            "applicable": True,
            "min_distance": round(gap, 4),
            "threshold": h07_threshold,
            "drink_object_id": d_obj.object_id,
            "electronics_object_id": e_obj.object_id,
            "separated": gap >= h07_threshold,
        }
    else:
        h07 = {"applicable": False, "min_distance": None, "threshold": h07_threshold,
               "drink_object_id": None, "electronics_object_id": None, "separated": None}

    per_object = []
    for o in norm_objs:
        cx, cy = _center(o.bbox_desk)
        z = zone_of(cx, cy, user_side)
        per_object.append({
            "object_id": o.object_id,
            "class_id": o.class_id,
            "class_name": o.class_name,
            "center": [round(cx, 4), round(cy, 4)],
            "area": round(_area(o.bbox_desk), 4),
            "zone_depth": z["depth"],
            "zone_lateral": z["lateral"],
            "fixed": o.fixed,
            "high_frequency": o.high_frequency,
            "source": o.source or None,
            # 确定性属性（颜色需原图 image + bbox_image，缺则 unknown；几何恒可算；语义 blocked）。
            "attributes": object_attributes(image, o.bbox_image, o.bbox_desk),
        })

    clusters = _cluster_by_class(norm_objs)

    return {
        "schema_version": SCENE_FACTS_VERSION,
        "user_side": user_side,
        "handedness": handedness,
        "mode": mode,
        "grid_resolution": n,
        "object_count": len(norm_objs),
        "objects": per_object,
        "zones": _zone_summary(per_object),
        "occupancy": {
            "occupied_ratio": round(occupied_ratio, 4),
            "free_ratio": round(free_ratio, 4),  # 总留白率（网格近似，标注分辨率）
        },
        "continuous_workspace": {
            "work_region_cells": mask_cells,
            "largest_empty_rect_ratio": round(cw_ratio, 4),
            "largest_empty_rect_desk": cw_rect,
        },
        "grouping": {
            "clusters": clusters,
            "functional_groups": group_entries,
            "grouping_score": grouping_score,
        },
        "alignment": {
            "mean_edge_deviation": round(mean_edge_dev, 4),
            "alignment_score": round(alignment_score, 4),
            "reference_lines": [round(v, 4) for v in _REF_LINES],
        },
        "accessibility": {
            "user_anchor": [round(user_anchor[0], 4), round(user_anchor[1], 4)],
            "mouse_side": handedness,
            "high_frequency_items": accessibility,
            "accessibility_score": accessibility_score,
        },
        "h07_separation": h07,
        "density": {
            "object_count": len(norm_objs),
            "occupied_ratio": round(occupied_ratio, 4),
            "fixed_count": sum(1 for o in norm_objs if o.fixed),
        },
    }


def _user_anchor(user_side: str, handedness: str) -> Tuple[float, float]:
    """用户偏好区锚点：靠用户侧、深度 t≈0.15、横向随惯用手偏置（鼠标偏好区）。"""
    lat = 0.62 if handedness == "right" else 0.38
    depth_t = 0.15
    if user_side == "bottom":
        return (lat, 1.0 - depth_t)
    if user_side == "top":
        return (lat, depth_t)
    if user_side == "left":
        return (depth_t, lat)
    return (1.0 - depth_t, lat)


def _zone_summary(per_object: Sequence[Dict]) -> Dict[str, int]:
    """九宫格计数（depth × lateral），用于“物品集中在哪一区”的描述。"""
    summary: Dict[str, int] = {}
    for o in per_object:
        key = f"{o['zone_lateral']}_{o['zone_depth']}"
        summary[key] = summary.get(key, 0) + 1
    return summary
