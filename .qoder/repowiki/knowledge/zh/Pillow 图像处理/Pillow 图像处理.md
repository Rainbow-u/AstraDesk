---
kind: external_dependency
name: Pillow 图像处理
slug: pillow
category: external_dependency
category_hints:
    - framework_behavior
scope:
    - '**'
source_files:
    - pyproject.toml
    - packages/vision/preprocessor.py
---

### 图像预处理
- 依赖声明于 `pyproject.toml`（`pillow>=10.0`），用于 EXIF 方向校正、去元数据、尺寸/像素上限校验、伪装格式拒绝（FR01）。
- 输入仅接受 JPEG/PNG（magic bytes 校验），单图 ≤10MB。