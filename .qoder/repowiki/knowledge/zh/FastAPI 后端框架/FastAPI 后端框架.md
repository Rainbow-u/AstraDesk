---
kind: external_dependency
name: FastAPI 后端框架
slug: fastapi
category: external_dependency
category_hints:
    - framework_behavior
scope:
    - '**'
source_files:
    - pyproject.toml
    - services/api/app.py
    - services/api/routes.py
---

### 后端 API 框架
- 声明于 `pyproject.toml`（`fastapi>=0.110`），由 `services/api/app.py` 装配，路由集中在 `services/api/routes.py`。
- 运行方式：WSL 内通过 `uvicorn services.api.app:app` 启动（real 模式，端口 8000）；健康检查 `/api/v1/health`、能力接口 `/api/v1/capabilities`、交互式文档 `/docs`。
- 前端在 Windows 侧经 Vite dev server 的同源 `/api` 代理访问后端，无需 CORS 白名单。
- 契约层：Pydantic Schema + JSON Schema（`contracts/`）双校验，错误统一为 PRD 8.3 格式。