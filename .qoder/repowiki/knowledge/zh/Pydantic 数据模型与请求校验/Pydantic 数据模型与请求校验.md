---
kind: external_dependency
name: Pydantic 数据模型与请求校验
slug: pydantic
category: external_dependency
category_hints:
    - framework_behavior
scope:
    - '**'
source_files:
    - pyproject.toml
    - services/api/schemas.py
---

### API 请求/响应模型
- 依赖声明于 `pyproject.toml`（`pydantic>=2.6`），用于 `services/api/schemas.py` 中的 Project/Asset/Job/Detection 等 Pydantic Schema，以及统一错误对象。
- 与 `contracts/*.schema.json` 共同构成 G1 契约校验（JSON Schema 用 `jsonschema` 库解析跨文件 `$ref`）。