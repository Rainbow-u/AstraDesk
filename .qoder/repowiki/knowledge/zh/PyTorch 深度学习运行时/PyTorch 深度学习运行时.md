---
kind: external_dependency
name: PyTorch 深度学习运行时
slug: pytorch
category: external_dependency
category_hints:
    - client_constraint
scope:
    - '**'
source_files:
    - pyproject.toml
    - artifacts/probe_torch_cuda_result.json
---

### GPU 推理运行时
- venv 位于 WSL 原生 `~/venvs/astradesk`（避开 `/mnt/d` drvfs 慢 I/O），代码仍从项目根运行。
- 运行时检测器缺依赖时显式报 `MODEL_UNAVAILABLE`，不静默回退到 CPU/mock。