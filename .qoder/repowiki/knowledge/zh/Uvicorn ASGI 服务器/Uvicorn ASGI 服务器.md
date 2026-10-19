---
kind: external_dependency
name: Uvicorn ASGI 服务器
slug: uvicorn
category: external_dependency
category_hints:
    - framework_behavior
scope:
    - '**'
source_files:
    - pyproject.toml
    - artifacts/start_api.sh
---

### WSL 后端进程入口
- 依赖声明于 `pyproject.toml`（`uvicorn>=0.29`），通过 `artifacts/start_api.sh` 后台启动 `uvicorn services.api.app:app`（real 模式，日志写 `WSL /tmp/astradesk_api.log`）。
- 与 FastAPI 配合提供 ASGI 服务，健康检查、优雅停止均经其生命周期管理。