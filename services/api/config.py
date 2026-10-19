"""运行配置（PRD FR13 运行模式；AGENTS.md 约定7 密钥只从服务端环境变量读取）。

运行模式：
- ``real``：真实模型推理。检测缺权重/依赖时直接报 ``MODEL_UNAVAILABLE``，不静默回退 mock。
- ``mock``：确定性 Mock，仅用于无 GPU 的契约测试与 demo，能力接口如实标注。

所有密钥（远端 VL/生成）仅从环境变量读取，不写入仓库、日志或前端。
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

VALID_RUN_MODES = ("real", "mock")


@dataclass(frozen=True)
class Settings:
    run_mode: str
    db_url: str
    data_root: Path
    weights_path: Path
    detector_device: str
    detector_conf: float
    # 开放词表融合（Phase 2）：默认关闭，mock/纯微调路径无需装配即可构造 Settings。
    openvocab_weights: Path = PROJECT_ROOT / "weights" / "yolov8s-world.pt"
    openvocab_enabled: bool = False
    openvocab_conf: float = 0.15
    fusion_iou: float = 0.5

    @property
    def is_real(self) -> bool:
        return self.run_mode == "real"


def _env(name: str, default: str) -> str:
    val = os.environ.get(name)
    return val if val not in (None, "") else default


def load_settings() -> Settings:
    """从环境变量装配设置。默认 mock，避免未配置时误触发真实模型/收费后端。"""
    run_mode = _env("ASTRADESK_RUN_MODE", "mock").lower()
    if run_mode == "demo":  # demo 等价 mock（PRD FR13：demo 与真实推理清楚区分）
        run_mode = "mock"
    if run_mode not in VALID_RUN_MODES:
        raise ValueError(f"ASTRADESK_RUN_MODE must be one of {VALID_RUN_MODES}, got {run_mode!r}")

    data_root = Path(_env("ASTRADESK_DATA_ROOT", str(PROJECT_ROOT / "data")))
    db_url = _env("ASTRADESK_DB_URL", f"sqlite:///{data_root / 'astradesk.db'}")
    weights_path = Path(_env("ASTRADESK_YOLO_WEIGHTS", str(PROJECT_ROOT / "weights" / "yolov10_desk_fine.pt")))
    device = _env("ASTRADESK_DEVICE", "")  # 空 → ultralytics 自动选 cuda/cpu
    conf = float(_env("ASTRADESK_DET_CONF", "0.25"))
    openvocab_weights = Path(_env("ASTRADESK_OPENVOCAB_WEIGHTS", str(PROJECT_ROOT / "weights" / "yolov8s-world.pt")))
    openvocab_enabled = _env("ASTRADESK_OPENVOCAB_ENABLED", "false").lower() in ("1", "true", "yes", "on")
    openvocab_conf = float(_env("ASTRADESK_OPENVOCAB_CONF", "0.15"))
    fusion_iou = float(_env("ASTRADESK_FUSION_IOU", "0.5"))

    return Settings(
        run_mode=run_mode,
        db_url=db_url,
        data_root=data_root,
        weights_path=weights_path,
        detector_device=device,
        detector_conf=conf,
        openvocab_weights=openvocab_weights,
        openvocab_enabled=openvocab_enabled,
        openvocab_conf=openvocab_conf,
        fusion_iou=fusion_iou,
    )
