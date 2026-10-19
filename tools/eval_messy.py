#!/usr/bin/env python3
"""Track2 评测：在**用户冻结照片集**上对比 微调 vs 微调+开放词表，产出结构化人工复核表。

设计（方案 Phase 2 / WORKFLOW 11.2）：
- 因用户照片无 GT，采用**结构化人工复核**：逐图列出两管线检出（类别/置信度/source/框），
  预留「真实物品数 / 漏检 / 误检」空栏由复核人填写 → 估算凌乱桌面 recall/precision + 漏检清单。
- **冻结集**：每图记 sha256 留档；本脚本只读照片、只写 artifacts，绝不改照片，
  产物**永不用于训练/调参**（D008 冻结评测集原则）。
- 外部阻塞：data/eval_raw 无照片时输出 blocked 报告并正常退出（不崩溃、不伪造数字）。

用法：
  ASTRADESK_DEVICE=0 python tools/eval_messy.py            # GPU（推荐，YOLO-World 热启 0.025s/图）
  python tools/eval_messy.py                                # 无 GPU 则 CPU（开放词表慢）
输出：artifacts/t_messy/eval_track2.json + review_worksheet.md
"""
import hashlib
import json
import os
import sys
import time
from pathlib import Path

from PIL import Image

from packages.vision import detector, fusion, open_vocab
from services.api.config import load_settings

RAW = Path("/mnt/d/AstraDesk/data/eval_raw")
OUTDIR = Path("/mnt/d/AstraDesk/artifacts/t_messy")
IMG_EXT = ("jpg", "jpeg", "png", "JPG", "JPEG", "PNG")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _photos():
    files = []
    for p in sorted(RAW.iterdir()) if RAW.exists() else []:
        if p.is_file() and p.suffix.lstrip(".") in IMG_EXT:
            files.append(p)
    return files


def _det_row(d: detector.Detection) -> dict:
    return {"class_id": d.class_id, "class_name": d.class_name,
            "confidence": round(d.confidence, 3), "source": d.source,
            "bbox_image": [round(x, 4) for x in d.bbox_image]}


def _write_blocked(photos_found: int) -> dict:
    report = {
        "status": "blocked",
        "reason": "data/eval_raw 无用户照片（仅投放说明）；Track2 依赖用户冻结集，外部阻塞。",
        "photos_found": photos_found,
        "note": "请把真实(尽量凌乱)桌面照片放入 data/eval_raw/ 后重跑本脚本；照片本地、gitignore、绝不参与训练/调参。",
    }
    OUTDIR.mkdir(parents=True, exist_ok=True)
    (OUTDIR / "eval_track2.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return report


def main() -> int:
    photos = _photos()
    if not photos:
        _write_blocked(0)
        return 2  # blocked（外部依赖），非失败

    st = load_settings()
    device = os.environ.get("ASTRADESK_DEVICE", st.detector_device) or ""
    finetuned = st.weights_path
    world = st.openvocab_weights

    records = []
    for p in photos:
        im = Image.open(p).convert("RGB")
        rec = {"image": p.name, "sha256": _sha256(p),
               "width": im.width, "height": im.height}

        # 管线 A：仅微调
        a = detector.detect_real(im, weights_path=finetuned, device=device, conf=st.detector_conf)
        rec["finetuned_only"] = {"count": len(a.detections),
                                 "detections": [_det_row(d) for d in a.detections],
                                 "elapsed_seconds": round(a.elapsed_seconds, 3)}

        # 管线 B：微调 + 开放词表融合（缺 YOLO-World 权重则如实标 unavailable，不静默跳过）
        if world.exists():
            t0 = time.perf_counter()
            b_raw = open_vocab.detect_open_vocab(im, weights_path=world, device=device,
                                                 conf=st.openvocab_conf)
            fused = fusion.fuse(a.detections, b_raw.detections, iou_thr=st.fusion_iou)
            rec["finetuned_plus_openvocab"] = {
                "openvocab_raw_count": len(b_raw.detections),
                "fused_count": len(fused),
                "detections": [_det_row(d) for d in fused],
                "added_by_openvocab": [_det_row(d) for d in fused if d.source == "yolo-world"],
                "elapsed_seconds": round(time.perf_counter() - t0, 3),
            }
        else:
            rec["finetuned_plus_openvocab"] = {
                "status": "MODEL_UNAVAILABLE",
                "reason": f"open-vocab weights not found: {world}",
            }

        # 人工复核空栏（由复核人填写，脚本不臆造 GT）
        rec["manual_review"] = {
            "true_object_count": None,
            "missed_by_finetuned": [],
            "missed_by_fusion": [],
            "false_positives": [],
            "notes": "",
        }
        records.append(rec)

    report = {
        "status": "needs_manual_review",
        "track": "Track2 (user frozen set)",
        "photos": len(records),
        "device": device or "auto",
        "finetuned_weights": str(finetuned),
        "openvocab_weights": str(world),
        "fusion_iou": st.fusion_iou,
        "openvocab_conf": st.openvocab_conf,
        "caveats": [
            "用户照片无 GT：recall/precision 需人工复核后估算，非自动计算",
            "冻结集：sha256 留档，绝不参与训练/调参（D008）",
            "凌乱桌面召回结论以本 Track2 人工复核为准，优先于 Track1 干净偏置数字",
        ],
        "records": records,
    }
    OUTDIR.mkdir(parents=True, exist_ok=True)
    (OUTDIR / "eval_track2.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_worksheet(report)
    print(json.dumps({"status": report["status"], "photos": len(records),
                      "out": str(OUTDIR / "eval_track2.json")}, ensure_ascii=False))
    return 0


def _write_worksheet(report: dict) -> None:
    """生成人工复核 markdown 工作表：逐图列两管线检出 + 待填空栏。"""
    lines = ["# Track2 人工复核工作表（用户冻结集）", "",
             f"- 照片数：{report['photos']}　设备：{report['device']}　融合 IoU：{report['fusion_iou']}",
             "- 说明：无 GT，请逐图对照原图填写「真实物品数 / 漏检 / 误检」；冻结集绝不参与训练/调参。", ""]
    for rec in report["records"]:
        lines.append(f"## {rec['image']}")
        lines.append(f"- sha256：`{rec['sha256']}`　尺寸：{rec['width']}×{rec['height']}")
        a = rec["finetuned_only"]
        lines.append(f"- 微调 only（{a['count']} 件，{a['elapsed_seconds']}s）："
                     + "、".join(f"{d['class_name']}{d['confidence']:.2f}" for d in a["detections"]))
        b = rec.get("finetuned_plus_openvocab", {})
        if b.get("status") == "MODEL_UNAVAILABLE":
            lines.append(f"- 微调+开放词表：{b['status']}（{b['reason']}）")
        else:
            added = "、".join(f"{d['class_name']}{d['confidence']:.2f}" for d in b.get("added_by_openvocab", []))
            lines.append(f"- 微调+开放词表（fused {b.get('fused_count')} 件，raw {b.get('openvocab_raw_count')}，"
                         f"{b.get('elapsed_seconds')}s）；开放词表新增：{added or '无'}")
        lines += ["- 真实物品数（人工填）：____", "- 微调漏检（人工填）：____",
                  "- 融合漏检（人工填）：____", "- 误检（人工填）：____", "- 备注：____", ""]
    (OUTDIR / "review_worksheet.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
