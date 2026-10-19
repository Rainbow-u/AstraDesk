---
kind: external_dependency
name: SQLAlchemy ORM（SQLite）
slug: sqlalchemy
category: external_dependency
category_hints:
    - sdk_real_api
scope:
    - '**'
source_files:
    - pyproject.toml
    - services/api/db.py
    - services/api/service.py
---

### 持久化层
- 依赖声明于 `pyproject.toml`（`sqlalchemy>=2.0`），数据库引擎指向项目根 `data/astradesk.db`（`services/api/db.py` 初始化 Engine/Session）。
- 模型：Project / Asset / Job / Detection（`service.py` 中定义），仓储逻辑集中在应用服务层，路由只做协议处理。
- 当前使用 SQLite；如需迁移需改 Engine 配置并同步 schema。