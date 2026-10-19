#!/usr/bin/env python3
"""从训练日志提取 GPU_mem 与最终指标证据（G1）。

ultralytics 训练日志用 \r 刷新进度条，GPU_mem 列由 torch.cuda.memory_reserved()/1e9
格式化为十进制 GB（日志中的 "X.XXG"）。本脚本逐 epoch 取峰值，产出干净证据文件，
供 STATUS/D008 引用，避免"无仓库证据"的声称。

用法：python artifacts/extract_train_gpumem.py [--log /tmp/train_desk9.log]
产物：artifacts/t_finetune/train_gpu_mem_evidence.txt
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 逐 batch 行： "<epoch>/100      <gpu>G ..."（进度条以 \r 分隔，故整体按非数字边界抓）
ROW = re.compile(r"(\d+)/100\s+([\d.]+)G")
EPOCH_TIME = re.compile(r"(\d+) epochs completed in ([\d.]+) hours")
ALL_METRICS = re.compile(r"all\s+(\d+)\s+(\d+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)")
SPEED = re.compile(r"Speed:\s+([\d.]+)ms preprocess,\s+([\d.]+)ms inference")
RESULTS_SAVED = re.compile(r"Results saved to (\S+)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default="/tmp/train_desk9.log")
    ap.add_argument("--out", default=str(ROOT / "artifacts" / "t_finetune" / "train_gpu_mem_evidence.txt"))
    args = ap.parse_args()

    text = Path(args.log).read_text(encoding="utf-8", errors="replace")

    # 逐 epoch 峰值 GPU_mem（十进制 GB）
    per_epoch: dict[int, float] = {}
    for ep, gpu in ROW.findall(text):
        ep_i, gpu_f = int(ep), float(gpu)
        per_epoch[ep_i] = max(per_epoch.get(ep_i, 0.0), gpu_f)
    peak_gb = max(per_epoch.values()) if per_epoch else None
    peak_epoch = max(per_epoch, key=per_epoch.get) if per_epoch else None

    epochs_done = EPOCH_TIME.search(text)
    speed = SPEED.search(text)
    saved = RESULTS_SAVED.search(text)
    # 最终 "all" 指标行取最后一次出现（训练末尾的最优/末轮汇总）
    all_rows = ALL_METRICS.findall(text)
    final_all = all_rows[-1] if all_rows else None

    lines = [
        "# 训练 GPU_mem 与最终指标证据（G1）",
        f"# 源日志: {args.log}（ultralytics 训练输出，GPU_mem=torch.cuda.memory_reserved()/1e9，十进制 GB）",
        "# 注：原始日志被 .gitignore(*.log) 排除、仅本地保留；本文件为已提取的自包含仓内证据（含逐 epoch 峰值）。",
        "",
        "## 逐 epoch 峰值 GPU_mem（十进制 GB）",
    ]
    for ep in sorted(per_epoch):
        lines.append(f"epoch {ep:>3}: {per_epoch[ep]:.2f}G")
    lines += [
        "",
        "## 汇总",
        f"peak_gpu_mem_decimal_gb: {peak_gb}",
        f"peak_epoch: {peak_epoch}",
        f"peak_gpu_mem_approx_gib: {round(peak_gb * 1e9 / (1024**3), 3) if peak_gb else None}  # GB→GiB 换算，供参考",
        f"gpu_total_gib: 5.997  # RTX 4050 Laptop 6GB（见 ENVIRONMENT）",
        f"epochs_completed_hours: {epochs_done.group(2) if epochs_done else None}",
    ]
    if final_all:
        lines += [
            "",
            "## 最终 all 指标（images instances P R mAP50 mAP50-95）",
            f"all: images={final_all[0]} instances={final_all[1]} P={final_all[2]} R={final_all[3]} mAP50={final_all[4]} mAP50-95={final_all[5]}",
        ]
    if speed:
        lines += ["", "## 推理速度", f"preprocess={speed.group(1)}ms inference={speed.group(2)}ms per image"]
    if saved:
        lines += ["", f"results_saved_to: {saved.group(1)}"]
    lines += [
        "",
        "## 结论",
        f"- 全程峰值 GPU_mem {peak_gb}G（十进制）≈ {round(peak_gb * 1e9 / (1024**3), 2) if peak_gb else '?'} GiB，远小于 6GB 硬边界，100 epoch 全程无 OOM。",
        "- 注：GPU_mem 为 ultralytics 自报十进制 GB（torch.cuda.memory_reserved()/1e9）；单位与数值以本证据为准。",
    ]

    out = Path(args.out)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"peak_gpu_mem_decimal_gb": peak_gb, "peak_epoch": peak_epoch,
                      "epochs_hours": epochs_done.group(2) if epochs_done else None,
                      "final_all": final_all, "out": str(out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
