"""Pydantic 契约模型与统一错误对象（PRD 8.3）。"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    """统一错误对象。"""

    code: str
    message: str
    details: Optional[dict] = None
    retryable: bool = False
    request_id: str = ""


class DetectionOut(BaseModel):
    id: str
    class_id: int
    class_name: str
    confidence: Optional[float] = None
    bbox_image: List[float] = Field(..., min_length=4, max_length=4)
    source: Optional[str] = None
    raw_class_name: Optional[str] = None  # 开放词表映射前原始提示词名(FR03 原始类可追溯)


class JobOut(BaseModel):
    id: str
    project_id: str
    type: str
    status: str
    stage: Optional[str] = None
    attempt: int = 1
    result: Optional[dict] = None
    detections: List[DetectionOut] = Field(default_factory=list)
    error: Optional[ErrorBody] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class AssetOut(BaseModel):
    id: str
    kind: str
    url: str
    width: int
    height: int
    sha256: str


class ProjectOut(BaseModel):
    id: str
    title: str
    created_at: Optional[str] = None
    assets: List[AssetOut] = Field(default_factory=list)


class ImageUploadOut(BaseModel):
    project_id: str
    image_asset_id: str
    thumbnail_asset_id: Optional[str] = None
    canonical_width: int
    canonical_height: int
    sha256: str


class DetectJobIn(BaseModel):
    image_asset_id: str


class InterpretObjectIn(BaseModel):
    """确认后的单个物品（FR04 人工校正结果）。bbox 用原图归一化坐标。"""

    object_id: Optional[str] = None
    class_name: str
    bbox_image: List[float] = Field(..., min_length=4, max_length=4)
    fixed: bool = False
    high_frequency: bool = False
    source: Optional[str] = None


class InterpretJobIn(BaseModel):
    """interpret 任务入参：在确认检测上跑确定性 facts + 模板 NL。

    物品来源二选一：显式 objects（优先）或 detect_job_id（拉取该任务持久化的检测）。
    desk_bbox_image 缺省为全图 [0,0,1,1]（FR02 要求提交前物品框在桌面范围内）。
    """

    desk_bbox_image: Optional[List[float]] = None
    user_side: str = "bottom"
    handedness: str = "right"
    mode: str = "office"
    detect_job_id: Optional[str] = None
    objects: Optional[List[InterpretObjectIn]] = None


class ProjectCreateIn(BaseModel):
    title: Optional[str] = "未命名项目"


class DetectorCapability(BaseModel):
    available: bool
    model_name: str
    model_version: str


class CapabilitiesOut(BaseModel):
    run_mode: str  # real / mock
    detector: DetectorCapability
    features: List[str] = Field(default_factory=list)
    open_vocab: Optional[dict] = None
