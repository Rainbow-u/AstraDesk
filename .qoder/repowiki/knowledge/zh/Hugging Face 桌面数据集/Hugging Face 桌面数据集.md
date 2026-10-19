---
kind: external_dependency
name: Hugging Face 桌面数据集
slug: huggingface-yolo-desk-dataset
category: external_dependency
category_hints:
    - client_constraint
scope:
    - '**'
source_files:
    - docs/DATASET.md
    - data/YOLO-DeskDataset/dataset/data.yaml
---

### 训练/验证数据集
- 仓库 `https://huggingface.co/datasets/hhh134/YOLO-DeskDataset`，许可 CC BY 4.0（可商用/修改，须署名作者 `hhh134`）。
- 实测 1646 张（train 1549 / val 97），YOLO txt 标注（`class_id cx cy w h`，归一化），80 类（id 0–79），总大小 1.34 GiB，通过 git-lfs 拉取。
- 注意：`dataset/data.yaml` 中 `path` 字段是作者本机绝对路径，使用前必须改写为本项目路径。