#!/usr/bin/env python3
"""生成权重 sha256 manifest（G2）。

对 weights/ 下的模型权重计算 sha256 与字节数，写 artifacts/weights_sha256.json，
供 ENVIRONMENT/DECISIONS 引用与复现校验（权重本身 gitignore、不入库，故以哈希留档）。

用法：python tools/weights_manifest.py
产物：artifacts/weights_sha256.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 权重来源与许可（人工核对，写入 manifest 的 note 字段）
NOTES = {
    "yolov10n.pt": "ultralytics assets v8.3.0，COCO 预训练，AGPL-3.0；Windows 侧经代理下载",
    "yolov10_desk9.pt": "tools/train_desk9.py 在 data/desk9(9 产品类) 迁移学习产出（起始 yolov10n.pt），AGPL-3.0",
    "yolov10_desk_fine.pt": "tools/train_desk_fine.py 在 data/desk_fine(version 2，23 训练类+other) 迁移学习产出（起始 yolov10n.pt），AGPL-3.0",
    "yolo26n.pt": "ultralytics AMP 校验时自动下载的小权重（非本项目检测权重），保留避免重下，AGPL-3.0",
    "yolov8s-world.pt": "YOLO-World s 变体，AGPL-3.0；Windows 侧经代理下载",
    "ViT-B-32.pt": "OpenAI CLIP 文本/图像编码器，首运行 YOLO-World 时自动下载缓存于 weights/clip/",
}


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights-dir", default=str(ROOT / "weights"))
    ap.add_argument("--out", default=str(ROOT / "artifacts" / "weights_sha256.json"))
    args = ap.parse_args()

    wdir = Path(args.weights_dir)
    entries = []
    for p in sorted(wdir.rglob("*.pt")):
        if not p.is_file():
            continue
        entries.append({
            "path": str(p.relative_to(ROOT)).replace("\\", "/"),
            "name": p.name,
            "bytes": p.stat().st_size,
            "sha256": sha256_of(p),
            "note": NOTES.get(p.name, ""),
        })

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generator": "tools/weights_manifest.py",
        "note": "权重文件本身被 .gitignore 排除、不入库；本 manifest 以 sha256 留档供复现校验。",
        "weights": entries,
    }
    out = Path(args.out)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"count": len(entries), "out": str(out),
                      "names": [e["name"] for e in entries]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
