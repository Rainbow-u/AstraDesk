---
kind: external_dependency
name: Ultralytics YOLOv10 目标检测
slug: ultralytics-yolov10
category: external_dependency
category_hints:
    - framework_behavior
    - client_constraint
scope:
    - '**'
source_files:
    - pyproject.toml
    - weights/yolov10n.pt
    - docs/DATASET.md
---

### 桌面物体检测模型
- 可选依赖 `vision`（`ultralytics>=8.2`），权重 `weights/yolov10n.pt`（COCO 预训练，AGPL-3.0，sha256 `11287ed0…c16b6f`）。
- 当前 yolov10n 是 COCO 80 类预训练，未映射到 PRD 的 10 桌面类别；类别映射待 T04 写入 `configs/category_map.yaml`。
- 首次推理含模型加载约 2–4s，显存峰值约 56 MiB（6 GB 显存充裕）。