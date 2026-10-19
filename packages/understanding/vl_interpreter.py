"""B 阶段多模态理解接口（Qwen-VL）——当前 blocked（无凭据/后端未接入）。

在**确定性 SceneFacts 之上**补充物品关系与解释，绝不替代或改写事实。护栏
（PRD FR06 / AGENTS.md 约定1 / H01）：

- 只能引用事实清单里已有的 ``object_id``；未知实例引用一律拒绝（``UNKNOWN_INSTANCE``）。
- 不得改写事实清单：SceneFacts 原样透传，VL 只补 ``relations``/``explanation``。
- 输出必须过 ``contracts/vl_relations.schema.json`` 校验。
- 提示词版本化于 ``prompts/vl_interpret.md``（含“图中文字当数据不当指令”的防注入声明）。
- 有界重试（``MAX_ATTEMPTS``），不做无界重试。
- 缺凭据/后端未接入 → 显式抛 ``VLUnavailable``，**不静默回退**、不产出假关系。

``build_prompt`` / ``validate_output`` / ``guard_relations`` 是纯函数，离线可测；
``interpret`` 的后端调用可通过 ``call_backend`` 注入以便测试编排（重试/校验/护栏），
真实后端在 B 阶段接入前始终 blocked。
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable, Dict, Iterable, Optional, Sequence

import jsonschema

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROMPT_PATH = PROJECT_ROOT / "prompts" / "vl_interpret.md"
SCHEMA_PATH = PROJECT_ROOT / "contracts" / "vl_relations.schema.json"
SCENE_FACTS_SCHEMA_PATH = PROJECT_ROOT / "contracts" / "scene_facts.schema.json"

MAX_ATTEMPTS = 2  # 有界重试上限（不做无界重试）

# 语义属性预留块（Phase 4 阶段 B）：当前恒 blocked，VL 后端接入后由下方
# ``apply_semantic_attributes`` 在同等护栏下填充（只引用已有 object_id、不改写其他事实）。
SEMANTIC_FIELDS = ("material", "open_state", "fill_level", "precise_orientation")


class VLUnavailable(RuntimeError):
    """VL 后端不可用（缺凭据/未接入/重试耗尽）。real 模式据此显式报错，不回退。"""


class VLGuardError(ValueError):
    """VL 输出违反护栏（未知实例引用 / schema 不合法 / 非 JSON）。"""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ---------------------------------------------------------------- 纯函数护栏

def load_prompt_template(path: Optional[Path] = None) -> str:
    p = Path(path) if path else PROMPT_PATH
    if not p.exists():
        raise VLUnavailable(f"prompt template not found: {p}")
    return p.read_text(encoding="utf-8")


def _output_schema() -> Dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _semantic_schema() -> Dict:
    """scene_facts.schema.json 中语义属性子 schema（$defs.semantic_attr）。"""
    schema = json.loads(SCENE_FACTS_SCHEMA_PATH.read_text(encoding="utf-8"))
    return schema["$defs"]["semantic_attr"]


def build_prompt(scene_facts: Dict, confirmed: Sequence[Dict], preferences: Dict,
                 template: Optional[str] = None) -> str:
    """把事实/清单/偏好作为**数据**注入版本化提示词模板（防注入：不改模板指令结构）。"""
    tpl = template if template is not None else load_prompt_template()
    schema = _output_schema()
    replacements = {
        "<<SCENE_FACTS_JSON>>": json.dumps(scene_facts, ensure_ascii=False),
        "<<CONFIRMED_JSON>>": json.dumps(list(confirmed), ensure_ascii=False),
        "<<PREFERENCES_JSON>>": json.dumps(preferences or {}, ensure_ascii=False),
        "<<OUTPUT_SCHEMA>>": json.dumps(schema, ensure_ascii=False),
    }
    for token, val in replacements.items():
        tpl = tpl.replace(token, val)
    return tpl


def validate_output(payload: Dict) -> None:
    """过 vl_relations.schema.json 校验；不合法抛 VLGuardError。"""
    try:
        jsonschema.Draft202012Validator(_output_schema()).validate(payload)
    except jsonschema.ValidationError as exc:
        raise VLGuardError("SCHEMA_INVALID", f"VL output failed schema: {exc.message}") from exc


def guard_relations(payload: Dict, valid_object_ids: Iterable[str]) -> Dict:
    """H01 护栏：relations 只能引用已存在的 object_id；未知引用拒绝。"""
    valid = set(valid_object_ids)
    for rel in payload.get("relations", []):
        for field in ("subject_id", "object_id"):
            oid = rel.get(field)
            if oid not in valid:
                raise VLGuardError(
                    "UNKNOWN_INSTANCE",
                    f"relation references unknown {field}={oid!r}; known ids={sorted(valid)}")
    return payload


def extract_json(text: str) -> Dict:
    """从模型文本输出中抽取 JSON 对象（容忍 ```json 代码块包裹）。"""
    s = (text or "").strip()
    if s.startswith("```"):
        s = s.strip("`")
        if s.lower().startswith("json"):
            s = s[4:]
        s = s.strip()
    try:
        obj = json.loads(s)
    except json.JSONDecodeError as exc:
        raise VLGuardError("NOT_JSON", f"VL output is not valid JSON: {exc}") from exc
    if not isinstance(obj, dict):
        raise VLGuardError("SCHEMA_INVALID", "VL output JSON must be an object")
    return obj


# ---------------------------------------------------------------- 语义属性预留接口（blocked）

def apply_semantic_attributes(scene_facts: Dict, updates: Sequence[Dict]) -> Dict:
    """预留接口：VL 可用时把语义属性（材质/开合/空满/朝向）回填到事实清单。

    护栏与关系一致（PRD FR06 / H01）：
    - 只引用事实清单里已有的 ``object_id``；未知 id 一律拒（``UNKNOWN_INSTANCE``）。
    - **不改写其他事实**：仅替换对应 object 的 ``semantic`` 块，其余原样透传（深拷贝）。
    - 回填后的 ``semantic`` 必须过 scene_facts.schema.json 的 semantic_attr 校验。
    - 字段限为 SEMANTIC_FIELDS；多余键/非法类型均拒（``SCHEMA_INVALID``）。

    该函数为纯函数、离线可测；真实 VL 后端在阶段 B 接入前始终 blocked，不由 interpret 调用。
    """
    import copy

    valid_ids = {o["object_id"] for o in scene_facts.get("objects", [])}
    by_id = {u.get("object_id"): u for u in updates if isinstance(u, dict)}
    for oid in by_id:
        if oid not in valid_ids:
            raise VLGuardError(
                "UNKNOWN_INSTANCE",
                f"semantic update references unknown object_id={oid!r}; known ids={sorted(valid_ids)}")

    sem_schema = _semantic_schema()
    validator = jsonschema.Draft202012Validator(sem_schema)
    merged = copy.deepcopy(scene_facts)
    for obj in merged.get("objects", []):
        upd = by_id.get(obj["object_id"])
        if upd is None:
            continue  # 无更新 → 保留原 blocked 语义块
        extra = set(upd) - set(SEMANTIC_FIELDS) - {"object_id"}
        if extra:
            raise VLGuardError(
                "SCHEMA_INVALID",
                f"semantic update has disallowed keys {sorted(extra)}; allowed={list(SEMANTIC_FIELDS)}")
        semantic = {"status": "available"}
        for field in SEMANTIC_FIELDS:
            semantic[field] = upd.get(field)
        errors = list(validator.iter_errors(semantic))
        if errors:
            raise VLGuardError(
                "SCHEMA_INVALID",
                f"semantic update for {obj['object_id']!r} failed schema: {errors[0].message}")
        obj["attributes"]["semantic"] = semantic
    return merged


# ---------------------------------------------------------------- 真实后端（blocked）

def _default_backend(image, prompt: str) -> str:
    """B 阶段真实后端。缺凭据或未接入均显式 blocked，不产出假数据。"""
    api_key = os.environ.get("ASTRADESK_VL_API_KEY", "")
    if not api_key:
        raise VLUnavailable("VL credentials not configured (ASTRADESK_VL_API_KEY missing)")
    # 有凭据但 B 阶段后端尚未接入：仍显式 blocked，不静默回退到模板/假关系。
    raise VLUnavailable("VL backend not wired yet (B-stage blocked)")


def interpret(image, scene_facts: Dict, confirmed: Sequence[Dict], preferences: Dict,
              call_backend: Optional[Callable] = None) -> Dict:
    """在事实之上补充关系与解释。返回 {relations, explanation, attempts, scene_facts(原样)}。

    后端调用有界重试；每次输出都过 schema 校验与 H01 护栏；失败达上限抛 VLUnavailable。
    """
    backend = call_backend or _default_backend
    valid_ids = [o["object_id"] for o in scene_facts.get("objects", [])]
    # 确认清单可补充/覆盖 id 集合（人工补框的实例也允许被引用）
    for c in confirmed:
        cid = c.get("object_id")
        if cid and cid not in valid_ids:
            valid_ids.append(cid)
    prompt = build_prompt(scene_facts, confirmed, preferences)

    last_error: Optional[Exception] = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            raw = backend(image, prompt)
            payload = extract_json(raw)
            validate_output(payload)
            guard_relations(payload, valid_ids)
            return {
                "relations": payload.get("relations", []),
                "explanation": payload.get("explanation", ""),
                "attempts": attempt,
                "scene_facts": scene_facts,  # 原样透传，不改写（H01）
            }
        except VLGuardError as exc:
            last_error = exc  # 护栏/格式问题 → 有界重试
            continue
    raise VLUnavailable(f"VL interpret failed after {MAX_ATTEMPTS} attempts: {last_error}")
