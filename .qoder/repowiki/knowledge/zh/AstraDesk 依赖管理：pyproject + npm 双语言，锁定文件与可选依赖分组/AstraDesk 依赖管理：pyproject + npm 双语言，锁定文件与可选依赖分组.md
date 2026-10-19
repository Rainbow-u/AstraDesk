---
kind: dependency_management
name: AstraDesk 依赖管理：pyproject + npm 双语言，锁定文件与可选依赖分组
category: dependency_management
scope:
    - '**'
source_files:
    - pyproject.toml
    - locks/python.lock.txt
    - apps/web/package.json
    - apps/web/package-lock.json
    - .gitignore
---

## 1. 使用的系统与工具

仓库采用**多语言、分层式**的依赖管理策略：
- **Python 后端/算法包**：使用 `setuptools`（`build-backend = "setuptools.build_meta"`）+ `pyproject.toml` 声明依赖，通过 `pip install -e .` 可编辑安装。
- **前端 Web 应用**：位于 `apps/web/`，使用 `npm`（`package.json` + `package-lock.json`），构建工具为 Vite + TypeScript。
- **Python 依赖锁定**：自定义锁定文件 `locks/python.lock.txt`（`pip freeze` 风格），而非 `requirements.txt` 或 `poetry.lock`。
- **无私有源配置**：未发现 `pip.conf`、`PYPI_URL`、`PIP_INDEX_URL`、`Pipfile`、`poetry.toml`、`uv.toml` 等私有注册表或镜像配置。

## 2. 关键文件

| 文件 | 作用 |
|---|---|
| `pyproject.toml` | Python 项目元数据、运行时依赖、可选依赖组、setuptools 包发现、pytest 配置 |
| `locks/python.lock.txt` | Python 全量依赖冻结快照（含 CUDA 版 torch、ultralytics 等） |
| `apps/web/package.json` | 前端运行时与开发依赖声明 |
| `apps/web/package-lock.json` | npm 依赖树锁定（由 npm 自动生成） |
| `.gitignore` | 排除 `node_modules/`、`dist/`、`.venv/`、`*.pt`/`*.pth` 等大体积二进制权重 |

## 3. 架构与约定

### Python 依赖分组
`pyproject.toml` 将依赖拆分为三类：
- **核心运行时**（`dependencies`）：`fastapi>=0.110`、`uvicorn>=0.29`、`pydantic>=2.6`、`sqlalchemy>=2.0`、`python-multipart>=0.0.9`、`pillow>=10.0`。
- **可选依赖组**（`[project.optional-dependencies]`）：
  - `dev`：`pytest>=8.0`、`httpx>=0.27`、`jsonschema>=4.21`。
  - `vision`：`torch>=2.2`、`ultralytics>=8.2`（GPU/CUDA 推理所需，体积大，按需安装）。
- **构建系统**：`setuptools>=68`，要求 `requires-python = ">=3.10"`。

包发现通过 `[tool.setuptools].packages` 显式列出 `services`、`services.api`、`services.worker`、`packages`、`packages.vision`、`packages.layout`、`packages.generation`，未使用自动发现。

### 锁定策略
- Python：`locks/python.lock.txt` 是完整 `pip freeze` 输出，包含所有可选依赖（torch、ultralytics、opencv-python、polars 等），并带有一行 `-e /mnt/d/AstraDesk` 的可编辑安装标记。该文件被纳入版本控制（不在 `.gitignore` 中），用于复现环境。
- Node：`apps/web/package-lock.json` 由 npm 生成，随代码提交；`node_modules/` 被忽略。

### 权重与大文件隔离
`.gitignore` 明确排除 `weights/*`、`*.pt`、`*.pth`、`*.onnx`、`*.safetensors`、`*.ckpt`、`*.bin` 以及 `data/*`（除 `.gitkeep` 占位符外），表明模型权重与数据集不作为依赖管理，而是本地单独维护。

## 4. 约定与约束

- **Python 依赖版本以 `>=` 宽松范围声明**（如 `fastapi>=0.110`、`pydantic>=2.6`），实际固定版本由 `locks/python.lock.txt` 提供（例如 fastapi==0.143.0、pydantic==2.14.0、torch==2.6.0+cu124）。这意味着 `pip install .` 可能拉取比最低版本更新的依赖，而 `pip install -r locks/python.lock.txt` 才会得到精确复现。
- **可选依赖必须显式安装**：vision 相关功能需通过 `pip install -e ".[vision]"` 安装，避免非 GPU 环境引入 torch 等重型依赖。
- **前端依赖使用 `^` 语义化版本范围**（如 `react: ^18.3.1`），由 `package-lock.json` 锁定具体解析结果。
- **无私有 PyPI 源**：仓库内未发现任何 `index-url`、`extra-index-url`、`PIP_INDEX_URL` 或 `PYPI_URL` 配置，默认使用官方 PyPI。
- **构建产物不入库**：`node_modules/`、`dist/`、`.venv/`、`__pycache__/`、`*.egg-info/` 均在 `.gitignore` 中被排除，仅保留源码与锁定文件。
- **测试依赖独立分组**：`pytest`、`httpx`、`jsonschema` 放在 `dev` 可选组中，生产运行不强制安装。