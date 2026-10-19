---
kind: configuration_system
name: AstraDesk 配置系统：基于环境变量 + dataclass Settings 的运行时装配
category: configuration_system
scope:
    - '**'
source_files:
    - services/api/config.py
    - docs/ENVIRONMENT.md
    - pyproject.toml
    - apps/web/vite.config.ts
    - artifacts/run_t02.sh
    - artifacts/start_api.sh
    - artifacts/run_t02_api.sh
---

## 1. 采用的方式

后端（FastAPI）与前端（Vite）各自通过**环境变量**加载运行期配置，没有引入 `.env` 解析库、YAML/JSON 配置文件或外部配置中心。核心实现集中在 `services/api/config.py`，以 Python `dataclasses.frozen` 定义不可变 `Settings` 对象，由 `load_settings()` 统一从 `os.environ` 装配。

## 2. 关键文件

- `services/api/config.py` — 唯一后端配置入口，定义 `Settings` dataclass 与 `load_settings()`。
- `docs/ENVIRONMENT.md` — 文档化已验证的环境基线、缺口与模型能力表，作为配置项的权威说明。
- `pyproject.toml` — 声明可选依赖 `vision=["torch>=2.2", "ultralytics>=8.2"]`，用于区分“纯 API”与“带视觉推理”的运行环境。
- `apps/web/vite.config.ts` — 前端 dev server 通过 `process.env.VITE_API_TARGET` 代理 `/api` 到后端。
- `artifacts/run_t02.sh` / `artifacts/start_api.sh` / `artifacts/run_t02_api.sh` — shell 脚本在启动前 `export ASTRADESK_*` 变量，是实际部署时注入配置的载体。

## 3. 架构与约定

### 3.1 后端 Settings 对象

`Settings` 为 frozen dataclass，字段如下：

| 字段 | 环境变量 | 默认值 | 说明 |
|---|---|---:|---|
| `run_mode` | `ASTRADESK_RUN_MODE` | `mock` | 仅允许 `real` 或 `mock`；`demo` 会被归一化为 `mock`（PRD FR13） |
| `db_url` | `ASTRADESK_DB_URL` | `sqlite:///{data_root}/astradesk.db` | SQLAlchemy 连接串 |
| `data_root` | `ASTRADESK_DATA_ROOT` | `PROJECT_ROOT/data` | 项目数据根目录 |
| `weights_path` | `ASTRADESK_YOLO_WEIGHTS` | `PROJECT_ROOT/weights/yolov10n.pt` | YOLOv10 权重路径 |
| `detector_device` | `ASTRADESK_DEVICE` | `""` | 空字符串 → ultralytics 自动选 cuda/cpu |
| `detector_conf` | `ASTRADESK_DET_CONF` | `0.25` | 检测置信度阈值（float） |

`is_real` 属性提供布尔判断，供上层逻辑分支 real/mock 行为。

### 3.2 环境变量读取规则

内部 `_env(name, default)` 使用 `os.environ.get(name)`，当值为 `None` 或空字符串 `""` 时回退到 default。这意味着设置 `ASTRADESK_X=`（空值）等价于未设置，会走默认分支。

### 3.3 运行模式约束

- `VALID_RUN_MODES = ("real", "mock")`，非法值直接抛 `ValueError`。
- `demo` 被显式映射为 `mock`，保证 demo 不触发真实推理。
- 注释明确：缺权重/依赖时 real 模式报 `MODEL_UNAVAILABLE`，**不静默回退 mock**。

### 3.4 密钥策略

配置模块 docstring 与 `docs/ENVIRONMENT.md` 共同约定：**所有密钥（远端 VL/生成）仅从服务端环境变量读取，不写入仓库、日志或前端**。当前无 `.env` 文件，密钥处于 blocked 状态（需用户提供凭据后注入）。shell 脚本中只暴露非敏感的路径与环境变量。

### 3.5 前端配置

`apps/web/vite.config.ts` 通过 `process.env.VITE_API_TARGET` 决定 dev proxy target，默认 `http://127.0.0.1:8000`。该变量仅影响开发阶段的前端代理，不参与构建产物。

### 3.6 启动入口

- 后端：`uvicorn services.api.app:app --reload`，需在进程环境中设置 `ASTRADESK_RUN_MODE=real`（见 `artifacts/start_api.sh`）。
- 测试：`artifacts/run_t02_api.sh` 将 `ASTRADESK_RUN_MODE=mock` 并指向 `artifacts/t02_api/data` 作为隔离数据根。
- 真实检测：`artifacts/run_t02.sh` 设置 `ASTRADESK_RUN_MODE=real` 与权重路径。

## 4. 观察到的约定与约束

- **约定**：所有后端可配置项均以 `ASTRADESK_` 前缀命名环境变量，集中由 `load_settings()` 一处读取，业务代码通过 `Settings` 实例访问，禁止直接 `os.environ` 散点调用。
- **约定**：`run_mode` 必须为 `real` 或 `mock`，其他值抛出 `ValueError`——这是代码层面真正执行的约束。
- **约定**：`ASTRADESK_DEVICE` 为空字符串表示“让 ultralytics 自动选择”，不为空时才传给底层。
- **约定**：密钥不进入仓库、日志或前端；当前仓库确实不存在 `.env` 文件，密钥注入依赖外部 shell 脚本或容器编排层。
- **约定**：可选依赖通过 `pyproject.toml` 的 `[project.optional-dependencies]` 划分 `dev` 与 `vision`，`vision` 组包含 torch/ultralytics，对应 real 模式所需的外部依赖。
- **约束**：`ASTRADESK_RUN_MODE` 不在 `VALID_RUN_MODES` 中即抛异常，属于硬校验。
- **约束**：`ASTRADESK_DET_CONF` 会经 `float()` 转换，传入非法数值会抛 `ValueError`。
- **约束**：`ASTRADESK_DATA_ROOT` 与 `ASTRADESK_YOLO_WEIGHTS` 会被 `Path()` 包装，传入非路径字符串会在后续文件系统操作时报错（类型检查不拦截）。

## 5. 局限

- 没有 `.env` 文件、Pydantic SettingsBase、python-dotenv 等常见配置框架，配置来源完全依赖进程环境变量。
- 没有配置 schema 校验（除 run_mode 白名单外），新增配置项需手动维护 docstring、`load_settings()` 与文档。
- 前端与后端配置互不感知，仅通过 Vite proxy 转发 `/api` 请求。
- 无 feature flag 机制，仅靠 `run_mode` 切换 real/mock 两条路径。