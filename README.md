# 桌面智能整理 · AstraDesk

用户上传桌面照片 → 识别物品 → 设置整理偏好 → 生成可编辑布局方案、整理步骤与效果图。
权威需求见 [`docs/PRD.md`](docs/PRD.md) 与 [`docs/WORKFLOW.md`](docs/WORKFLOW.md)；执行规则见 [`AGENTS.md`](AGENTS.md)。

当前进度见 [`docs/STATUS.md`](docs/STATUS.md)。已交付：**T00 环境基线、T01 检测子项、T02 契约与骨架 + 桌面识别端到端**。

## 目录结构

```
apps/web/            前端（React + TS + Vite）：上传页 + 检测叠框
services/api/        FastAPI：路由 / 应用服务 / 仓储 / 契约 Schema / 配置
services/worker/     任务执行入口（python -m services.worker）
packages/vision/     检测适配器（YOLOv10 + Mock）、图像预处理
packages/layout/     坐标契约转换（bbox_image ↔ bbox_desk）
packages/generation/ 生成与评估适配器（B 阶段，待凭据）
contracts/           JSON Schema 与合法/非法样例（G1 单一来源）
configs/ prompts/    版本化配置与提示词（后续任务填充）
tests/               pytest：契约、坐标往返、检测端到端
artifacts/           运行证据（图片/大文件不入库）
docs/                PRD / WORKFLOW / STATUS / ENVIRONMENT / DECISIONS / DATASET
locks/               依赖锁（Python）
data/ weights/       本地数据与权重（gitignore，不入库）
```

## 运行环境

- **编辑**：Windows；**运行**：WSL2 Ubuntu-24.04（GPU：RTX 4050 Laptop 6GB，CUDA 12.4）。
- Python venv：`~/venvs/astradesk`（WSL 原生文件系统，避开 `/mnt/d` 慢 I/O）。
- 前端 Node：Windows 侧 Node v24。
- 详见 [`docs/ENVIRONMENT.md`](docs/ENVIRONMENT.md)。

## 后端安装与启动（WSL）

```bash
# 依赖锁见 locks/python.lock.txt；开发依赖见 pyproject [project.optional-dependencies]
~/venvs/astradesk/bin/pip install -e '.[dev]'        # API + 测试
~/venvs/astradesk/bin/pip install -e '.[vision]'     # 真实检测（torch/ultralytics）

# 启动 API（默认 mock 模式；真实检测设 ASTRADESK_RUN_MODE=real）
ASTRADESK_RUN_MODE=real \
ASTRADESK_YOLO_WEIGHTS=weights/yolov10n.pt \
~/venvs/astradesk/bin/python -m uvicorn services.api.app:app --host 127.0.0.1 --port 8000

# 可选：独立 worker（轮询执行 queued 检测任务）
~/venvs/astradesk/bin/python -m services.worker
```

健康检查：`GET http://127.0.0.1:8000/api/v1/health`；能力：`GET /api/v1/capabilities`；
交互式文档：`http://127.0.0.1:8000/docs`。

## 前端安装与启动（Windows）

```powershell
cd apps\web
npm install
npm run dev      # http://localhost:5173，/api 代理到 127.0.0.1:8000
npm run build    # 产出 dist/
```

## 测试

```bash
# WSL，项目根
ASTRADESK_RUN_MODE=mock ~/venvs/astradesk/bin/python -m pytest -q
```

覆盖：契约合法/非法样例校验、坐标往返一致性、检测端到端（mock）、
真实模式权重缺失报 `MODEL_UNAVAILABLE` 不静默回退。

## 运行模式（PRD FR13 / AGENTS.md 约定1）

- `real`：真实模型推理；检测缺权重/依赖直接报 `MODEL_UNAVAILABLE`，**不静默回退 mock**。
- `mock`：确定性 Mock，仅用于无 GPU 的契约测试与 demo，能力接口如实标注 `mock-detector`。
- 环境变量：`ASTRADESK_RUN_MODE`、`ASTRADESK_DB_URL`、`ASTRADESK_DATA_ROOT`、
  `ASTRADESK_YOLO_WEIGHTS`、`ASTRADESK_DEVICE`、`ASTRADESK_DET_CONF`。
- 远端 VL/生成密钥仅从服务端环境变量读取，不入仓库/前端/日志。

## 许可提示

- 数据集 YOLO-DeskDataset：CC BY 4.0（须署名），见 [`docs/DATASET.md`](docs/DATASET.md)。
- YOLOv10 / ultralytics：AGPL-3.0，闭源/商用分发需许可评估。
