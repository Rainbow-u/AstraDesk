"""把 SceneFacts 模板化为中文场景描述与布局解释（Phase 3 facts-first NL）。

原则：
- **只用事实**：所有数字/实例都取自传入的 SceneFacts（H01 单一事实来源），不臆造、不改写。
- **绑定 PRD 6.2 软目标**：用可测量维度（占比/距离/偏差/评分）描述“美学”，不用空洞形容词。
- **离线、确定性、可测试**：无随机、无网络、无模型；同输入同输出。
- **诚实标注**：reduced-movement（减少移动）是规划期指标（需目标布局），场景描述阶段标 N/A；
  留白率/连续工作区注明网格分辨率与“图像空间非物理量”（PRD 5.2）。
"""
from __future__ import annotations

from typing import Dict, List, Optional

RENDER_VERSION = "1.0"

# PRD 6.2 软目标权重（仅用于在描述中标注相对重要性；不在此合成总分，避免过度声称）
SOFT_GOAL_WEIGHTS = {
    "continuous_workspace": 0.35,
    "accessibility": 0.25,
    "grouping": 0.20,
    "alignment": 0.10,
    "movement_saving": 0.10,
}

# 产品类中文名（PRD 5.1，version 2 词表 24 类；未命中者 _zh 回退英文名）
CLASS_ZH = {
    "laptop": "笔记本电脑", "monitor": "显示器", "keyboard": "键盘", "mouse": "鼠标",
    "mobile_phone": "手机", "book": "书", "pen": "笔",
    "cup": "杯子", "thermos_cup": "保温杯", "plastic_cup": "塑料杯", "disposable_cup": "一次性杯",
    "bottle": "瓶子", "plastic_bottle": "塑料瓶", "squeeze_bottle": "挤压瓶", "can": "易拉罐",
    "waterpot": "水壶",
    "cable": "数据线", "charger": "充电器", "tissue": "纸巾", "paper": "纸张",
    "lamp": "台灯", "headphones": "耳机", "mouse_pad": "鼠标垫",
    "other": "其他",
}
GROUP_ZH = {"electronics": "电子设备组", "writing": "书写组", "drinkware": "杯瓶组", "other": "其他组"}
DEPTH_ZH = {"near": "近", "mid": "中", "far": "远"}
LATERAL_ZH = {"left": "左", "center": "中", "right": "右", "top": "上", "middle": "中", "bottom": "下"}
MODE_ZH = {"study": "学习", "office": "办公", "minimal": "简约"}
USER_SIDE_ZH = {"bottom": "下侧", "top": "上侧", "left": "左侧", "right": "右侧"}

# 几何属性中文名（Phase 4 阶段 B）：orientation 为 landscape/portrait 才有自然措辞，square 略去
ORIENT_ZH = {"landscape": "横放", "portrait": "竖放"}
SIZE_ZH = {"small": "小号", "medium": "中号", "large": "大号"}
UNKNOWN_COLOR = "unknown"


class RenderError(ValueError):
    """facts 结构缺失关键字段（应先过 schema 校验，这里是防御性检查）。"""


def _pct(x: Optional[float]) -> str:
    return "—" if x is None else f"{x * 100:.1f}%"


def _num(x: Optional[float], nd: int = 2) -> str:
    return "—" if x is None else f"{x:.{nd}f}"


def _zh(class_name: str) -> str:
    return CLASS_ZH.get(class_name, class_name)


def _zone_zh(obj: Dict) -> str:
    return f"{LATERAL_ZH.get(obj['zone_lateral'], obj['zone_lateral'])}·{DEPTH_ZH.get(obj['zone_depth'], obj['zone_depth'])}"


def _color_prefix(attrs: Dict) -> str:
    """颜色前缀：仅在取到真实主色时加“X色”；unknown 不加（不编造）。"""
    name = (attrs.get("color") or {}).get("name")
    if not name or name == UNKNOWN_COLOR:
        return ""
    return f"{name}色"


def _geometry_tag(attrs: Dict) -> List[str]:
    """几何派生词（orientation/size）；square 无自然朝向词则略去。"""
    tags = []
    orient = ORIENT_ZH.get(attrs.get("orientation"))
    if orient:
        tags.append(orient)
    size = SIZE_ZH.get(attrs.get("size_class"))
    if size:
        tags.append(size)
    return tags


def _composition_line(facts: Dict) -> str:
    """物品构成 + 分区 + 颜色/几何，例如：蓝色杯子(左·中,竖放,小号)、笔记本电脑(中·近,横放,大号,固定)…"""
    parts = []
    for o in facts["objects"]:
        attrs = o.get("attributes") or {}
        inner = [_zone_zh(o)] + _geometry_tag(attrs)
        if o.get("fixed"):
            inner.append("固定")
        if o.get("high_frequency"):
            inner.append("常用")
        parts.append(f"{_color_prefix(attrs)}{_zh(o['class_name'])}({','.join(inner)})")
    head = f"桌面共 {facts['object_count']} 件物品"
    if not parts:
        return head + "（未检出有效物品）。"
    return head + "：" + "、".join(parts) + "。"


def _continuous_workspace_line(facts: Dict) -> str:
    cw = facts["continuous_workspace"]
    gridn = facts["grid_resolution"]
    rect = cw.get("largest_empty_rect_desk")
    where = ""
    if rect:
        cx, cy = (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2
        lat = "左" if cx < 1 / 3 else ("右" if cx >= 2 / 3 else "中")
        dep = "近" if cy >= 2 / 3 else ("远" if cy < 1 / 3 else "中")
        where = f"，位于桌面{lat}侧偏{dep}端"
    return (f"中间偏近用户区域的最大连续空闲矩形占该区 {_pct(cw['largest_empty_rect_ratio'])}"
            f"（{gridn}×{gridn} 网格近似{where}）。")


def _accessibility_line(facts: Dict) -> str:
    acc = facts["accessibility"]
    side = "右手" if acc["mouse_side"] == "right" else "左手"
    items = acc["high_frequency_items"]
    if not items:
        return f"未标记常用物品；惯用手为{side}，鼠标偏好区在中偏{'右' if acc['mouse_side']=='right' else '左'}近端。"
    detail = "、".join(f"{_zh(it['class_name'])} 距用户偏好区 {_num(it['distance_to_user_region'])}"
                       for it in items)
    score = acc.get("accessibility_score")
    return f"惯用手{side}；常用物品取用便利：{detail}（对角归一，越小越顺手），便利评分 {_num(score)}。"


def _grouping_lines(facts: Dict) -> List[str]:
    lines = []
    g = facts["grouping"]
    for entry in g["functional_groups"]:
        if entry["count"] < 2:
            continue
        lines.append(f"{GROUP_ZH.get(entry['group'], entry['group'])}（{entry['count']} 件）"
                     f"平均两两中心距 {_num(entry['avg_pairwise_distance'])}，集中度评分 {_num(entry['grouping_score'])}。")
    for c in g["clusters"]:
        if c["count"] >= 2:
            lines.append(f"{_zh(c['class_name'])} {c['count']} 个聚在一处（质心 {c['centroid'][0]:.2f},{c['centroid'][1]:.2f}）。")
    if not lines:
        lines.append("无可聚类的同类/同组物品（多为单件）。")
    return lines


def _alignment_line(facts: Dict) -> str:
    a = facts["alignment"]
    return (f"物品边缘到参考线（三分布尔线）的平均偏差 {_num(a['mean_edge_deviation'], 3)}，"
            f"对齐评分 {_num(a['alignment_score'])}（越接近 1 越齐整）。")


def _whitespace_line(facts: Dict) -> str:
    occ = facts["occupancy"]
    return f"总留白率约 {_pct(occ['free_ratio'])}（{facts['grid_resolution']}×{facts['grid_resolution']} 网格近似，占用 {_pct(occ['occupied_ratio'])}）。"


def _h07_status(facts: Dict):
    """返回 (信息行, 告警行)。仅未分隔时产生 warning（H07 硬约束）。"""
    h = facts["h07_separation"]
    if not h.get("applicable"):
        return None, []
    if h.get("separated"):
        note = (f"杯瓶与电子设备最短距离 {_num(h['min_distance'])} ≥ 阈值 {_num(h['threshold'])}，"
                f"已分隔（H07 布局启发式）。")
        return note, []
    warn = (f"注意：杯瓶（{h['drink_object_id']}）与电子设备（{h['electronics_object_id']}）"
            f"最短距离 {_num(h['min_distance'])} < 阈值 {_num(h['threshold'])}，建议在规划中拉开（H07）。")
    return warn, [warn]


def _density_line(facts: Dict) -> str:
    d = facts["density"]
    fixed = f"，其中固定 {d['fixed_count']} 件" if d["fixed_count"] else ""
    return f"密度：{d['object_count']} 件物品占用桌面 {_pct(d['occupied_ratio'])}{fixed}。"


def render(facts: Dict) -> Dict:
    """渲染场景描述与布局解释。返回结构化 dict（含可直接展示的 text）。"""
    for key in ("objects", "continuous_workspace", "accessibility", "grouping",
                "alignment", "occupancy", "h07_separation", "density"):
        if key not in facts:
            raise RenderError(f"facts missing required key: {key}")

    mode_zh = MODE_ZH.get(facts.get("mode", ""), facts.get("mode", ""))
    side_zh = USER_SIDE_ZH.get(facts.get("user_side", ""), facts.get("user_side", ""))

    dimensions = [
        {"key": "continuous_workspace", "weight": SOFT_GOAL_WEIGHTS["continuous_workspace"],
         "text": _continuous_workspace_line(facts)},
        {"key": "accessibility", "weight": SOFT_GOAL_WEIGHTS["accessibility"],
         "text": _accessibility_line(facts)},
        {"key": "grouping", "weight": SOFT_GOAL_WEIGHTS["grouping"],
         "text": " ".join(_grouping_lines(facts))},
        {"key": "alignment", "weight": SOFT_GOAL_WEIGHTS["alignment"],
         "text": _alignment_line(facts)},
        {"key": "movement_saving", "weight": SOFT_GOAL_WEIGHTS["movement_saving"],
         "text": "减少移动为规划期指标（需对比目标布局），场景描述阶段不适用（N/A）。"},
    ]

    h07_note, warnings = _h07_status(facts)
    summary = _composition_line(facts)

    text_lines = [
        f"【场景描述】(整理模式：{mode_zh}；靠用户侧：{side_zh})",
        summary,
        _density_line(facts),
        _whitespace_line(facts),
        "",
        "【按可测量维度的布局解释】",
    ]
    for dim in dimensions:
        text_lines.append(f"- {_dim_zh(dim['key'])}(权重{dim['weight']:.2f})：{dim['text']}")
    if h07_note and not warnings:
        text_lines.append("")
        text_lines.append("【硬约束状态】")
        text_lines.append(f"- {h07_note}")
    if warnings:
        text_lines.append("")
        text_lines.append("【硬约束提示】")
        text_lines.extend(f"- {w}" for w in warnings)
    text_lines.append("")
    text_lines.append("注：以上距离/面积均为桌面归一化图像空间下的相对量，非厘米物理量（未经相机标定）。"
                      "颜色为受光照/白平衡影响的主色近似；材质/开合/空满等语义属性暂未启用（blocked），描述不含相关推断。")

    return {
        "render_version": RENDER_VERSION,
        "mode": facts.get("mode"),
        "user_side": facts.get("user_side"),
        "summary": summary,
        "dimensions": dimensions,
        "h07_note": h07_note,
        "warnings": warnings,
        "text": "\n".join(text_lines),
    }


def _dim_zh(key: str) -> str:
    return {
        "continuous_workspace": "连续工作区",
        "accessibility": "取用便利",
        "grouping": "同类集中",
        "alignment": "对齐有序",
        "movement_saving": "减少移动",
    }.get(key, key)
