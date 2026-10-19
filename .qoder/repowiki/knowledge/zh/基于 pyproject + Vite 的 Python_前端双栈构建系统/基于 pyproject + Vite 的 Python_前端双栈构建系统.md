---
kind: build_system
name: 基于 pyproject + Vite 的 Python/前端双栈构建系统
category: build_system
scope:
    - '**'
source_files:
    - pyproject.toml
    - locks/python.lock.txt
    - apps/web/package.json
    - apps/web/vite.config.ts
    - apps/web/tsconfig.json
    - artifacts/run_t01.sh
    - artifacts/run_t02.sh
    - artifacts/start_api.sh
    - artifacts/probe_wsl.sh
    - docs/ENVIRONMENT.md
---

## 1. 总体方案

仓库采用**多语言、多产物**的构建方式：
- **Python 后端与算法包**：使用 `setuptools`（`build-backend = setuptools.build_meta`，requires >=68），通过根级 `pyproject.toml` 声明依赖、可选依赖与可安装包集合。
- **前端 Web 应用**：位于 `apps/web/`，使用 Vite 5 + React 18 + TypeScript 5，通过 `npm run build`（先 `tsc` 再 `vite build`）产出静态资源到 `apps/web/dist/`。
- **无 CI/Dockerfile/Makefile**：仓库根没有 `.github/workflows`、`Dockerfile`、`Makefile`、`tox.ini` 等自动化流水线文件；部署脚本以 `artifacts/*.sh` 形式存在，属于一次性运行脚本而非持续集成配置。

## 2. 关键文件

| 文件 | 作用 |
|---|---|
| `pyproject.toml` | Python 项目元数据、依赖、可选依赖 (`dev`, `vision`)、setuptools 包清单、pytest 配置 |
| `locks/python.lock.txt` | pip 锁定的完整依赖树（含 `-e /mnt/d/AstraDesk` 可编辑安装行） |
| `apps/web/package.json` | 前端 npm 脚本与依赖 |
| `apps/web/vite.config.ts` | Vite dev server 端口 5173，`/api` 代理到 `http://127.0.0.1:8000`（可通过 `VITE_API_TARGET` 覆盖） |
| `apps/web/tsconfig.json` | TypeScript 编译配置 |
| `artifacts/run_t01.sh`, `artifacts/run_t02.sh`, `artifacts/start_api.sh` | 检测任务与 API 启动的一次性 shell 脚本 |
| `artifacts/probe_wsl.sh` | WSL 环境探针脚本 |
| `docs/ENVIRONMENT.md` | 记录已验证的前端构建命令 `npm run build` 及产物 `dist/` |

## 3. 架构与约定

### Python 侧
- 构建后端固定为 `setuptools.build_meta`，要求 `setuptools>=68`。
- 包名 `astradesk`，版本 `0.1.0`，要求 `python>=3.10`。
- 运行时依赖集中在 `[project]` 段：fastapi、uvicorn、pydantic、sqlalchemy、python-multipart、pillow。
- 可选依赖拆分为 `dev`（pytest, httpx, jsonschema）和 `vision`（torch, ultralytics），便于按需安装。
- 可安装包由 `[tool.setuptools].packages` 显式列出：`services`, `services.api`, `services.worker`, `packages`, `packages.vision`, `packages.layout`, `packages.generation`。
- pytest 通过 `[tool.pytest.ini_options]` 配置，测试目录固定为 `tests`，默认加 `-q` 参数。
- 依赖锁定通过 `pip freeze > locks/python.lock.txt` 生成，README 明确“依赖锁见 locks/python.lock.txt”。

### 前端侧
- `apps/web/package.json` 定义三个脚本：`dev`（vite）、`build`（`tsc && vite build`）、`preview`（vite preview）。
- 构建流程是**两步**：先用 TypeScript 编译器做类型检查，再用 Vite 打包。`docs/ENVIRONMENT.md` 确认该流程在 Windows Node v24 上已通过。
- 开发时 Vite dev server 监听 5173，并通过反向代理将 `/api` 请求转发到后端（默认 `http://127.0.0.1:8000`），环境变量 `VITE_API_TARGET` 可覆盖目标地址。

### 产物与发布
- Python 包通过 `pip install -e .`（可编辑模式，见 `locks/python.lock.txt` 中的 `-e /mnt/d/AstraDesk`）或 `pip install .` 安装。
- 前端静态资源输出到 `apps/web/dist/`，`.gitignore` 忽略 `build/` 与 `node_modules/`。
- 权重文件 `weights/yolov10n.pt` 作为预训练模型随仓库分发（AGPL-3.0，见 `docs/ENVIRONMENT.md` 许可说明）。

## 4. 约定与约束

- **Python 构建工具链**：必须使用 setuptools ≥68 作为 build backend（`pyproject.toml` 强制）。`requires-python = ">=3.10"` 是硬性约束。
- **依赖范围**：运行时依赖与可选依赖严格分离于 `pyproject.toml` 的 `[project]` 与 `[project.optional-dependencies]` 两段，新增依赖需落在此处而非手写 requirements.txt。
- **依赖锁定**：生产复现应基于 `locks/python.lock.txt`（README 明确指向该文件），其中包含可编辑安装行 `-e /mnt/d/AstraDesk`，表明本地开发以 editable install 为主。
- **测试入口**：统一通过 `pytest`（`[tool.pytest.ini_options]` 指定 testpaths=`tests`），新增测试需放在 `tests/` 下。
- **前端构建命令**：`cd apps/web; npm run build` 是文档记录的官方构建入口，产出 `dist/`；开发入口为 `npm run dev`。
- **前后端联调**：前端通过 Vite proxy 把 `/api` 转发到后端 8000 端口，这是约定的本地联调方式（`vite.config.ts` 中硬编码 target，仅可通过 `VITE_API_TARGET` 环境变量覆盖）。
- **无容器化与 CI**：仓库未发现 Dockerfile、docker-compose、GitHub Actions 或其他 CI 配置文件；部署脚本集中于 `artifacts/` 目录，属于手动执行脚本而非自动化流水线。