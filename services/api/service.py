"""应用服务与仓储（AGENTS.md：路由只做协议处理，业务规则在此）。

覆盖 T02 桌面识别端到端：创建项目 → 上传图像（预处理/存储）→ 创建检测任务 →
worker 执行真实/Mock 检测 → 坐标还原 → 结果查询。持久化用 SQLite + SQLAlchemy。
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from PIL import Image
from sqlalchemy.orm import Session

from packages.layout.coordinates import CoordinateError, image_to_desk
from packages.understanding import render_nl, scene_facts
from packages.understanding.scene_facts import SceneFactsError, SceneObject
from packages.vision import detector, fusion, open_vocab
from packages.vision.preprocess import PreprocessError, preprocess, to_bytes

from . import storage
from .config import Settings
from .db import Asset, Detection, Job, Project
from .errors import ApiError

SUPPORTED_EXT = {"jpg", "jpeg", "png"}


def _now_iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _ext_of(filename: str) -> str:
    ext = Path(filename or "").suffix.lower().lstrip(".")
    if ext not in SUPPORTED_EXT:
        raise ApiError("INVALID_IMAGE", f"unsupported file type: {ext or '(none)'}", status_code=415)
    return ext


# ---------------------------------------------------------------- 项目

def create_project(session: Session, title: str = "未命名项目") -> Project:
    proj = Project(id=uuid.uuid4().hex, title=title or "未命名项目")
    session.add(proj)
    session.commit()
    return proj


def get_project(session: Session, project_id: str) -> Project:
    proj = session.get(Project, project_id)
    if proj is None or proj.deleted_at is not None:
        raise ApiError("PROJECT_NOT_FOUND", f"project not found: {project_id}", status_code=404)
    return proj


def list_projects(session: Session, limit: int = 50, offset: int = 0) -> List[Project]:
    return (
        session.query(Project)
        .filter(Project.deleted_at.is_(None))
        .order_by(Project.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )


# ---------------------------------------------------------------- 图像上传

def upload_image(session: Session, settings: Settings, project_id: str,
                 filename: str, raw: bytes) -> dict:
    """校验并存储图像：预处理 → 标准图 canonical + 缩略图。返回 image_id 与尺寸。"""
    get_project(session, project_id)  # 归属校验
    ext = _ext_of(filename)
    if len(raw) == 0:
        raise ApiError("INVALID_IMAGE", "empty file", status_code=400)

    try:
        canonical = preprocess(raw, ext)
    except PreprocessError as exc:
        status = 413 if "10MB" in exc.message or "megapixel" in exc.message else 400
        raise ApiError(exc.code, exc.message, status_code=status)

    canon_bytes = to_bytes(canonical)
    canon_ext = "png" if canonical.format == "PNG" else "jpg"
    canon_asset = storage.store_image(settings.data_root, project_id, "canonical", canon_bytes, canon_ext)
    thumb_asset = storage.make_thumbnail(settings.data_root, canon_bytes, project_id)

    session.add(Asset(id=canon_asset.asset_id, project_id=project_id, kind="canonical",
                      path=canon_asset.rel_path, sha256=canon_asset.sha256,
                      width=canon_asset.width, height=canon_asset.height))
    session.add(Asset(id=thumb_asset.asset_id, project_id=project_id, kind="thumbnail",
                      path=thumb_asset.rel_path, sha256=thumb_asset.sha256,
                      width=thumb_asset.width, height=thumb_asset.height))
    session.commit()

    return {
        "project_id": project_id,
        "image_asset_id": canon_asset.asset_id,
        "thumbnail_asset_id": thumb_asset.asset_id,
        "canonical_width": canon_asset.width,
        "canonical_height": canon_asset.height,
        "sha256": canon_asset.sha256,
    }


def get_asset(session: Session, asset_id: str) -> Asset:
    asset = session.get(Asset, asset_id)
    if asset is None:
        raise ApiError("ASSET_NOT_FOUND", f"asset not found: {asset_id}", status_code=404)
    get_project(session, asset.project_id)  # 项目删除后不可读取
    return asset


# ---------------------------------------------------------------- 检测任务

def create_detect_job(session: Session, project_id: str, image_asset_id: str) -> Job:
    get_project(session, project_id)
    asset = get_asset(session, image_asset_id)
    if asset.project_id != project_id:
        raise ApiError("ASSET_NOT_FOUND", "asset does not belong to project", status_code=404)
    job = Job(id=uuid.uuid4().hex, project_id=project_id, type="detect",
              status="queued", stage="detecting", attempt=1, image_asset_id=image_asset_id)
    session.add(job)
    session.commit()
    return job


def process_detect_job(session: Session, settings: Settings, job_id: str) -> Job:
    """worker 执行检测任务：queued → running → succeeded/failed。

    real 模式检测不可用时置 failed 并记录 MODEL_UNAVAILABLE，不静默回退 mock（约定1）。
    终态不被重复处理覆盖（约定4）。
    """
    job = session.get(Job, job_id)
    if job is None:
        raise ApiError("JOB_NOT_FOUND", f"job not found: {job_id}", status_code=404)
    if job.status in ("succeeded", "failed", "cancelled"):
        return job  # 已是终态，直接返回

    job.status = "running"
    job.stage = "detecting"
    session.commit()
    ov_result = None

    try:
        asset = session.get(Asset, job.image_asset_id)
        if asset is None:
            raise ApiError("ASSET_NOT_FOUND", "image asset missing", status_code=404)
        with Image.open(asset.path) as im:
            im.load()
            img = im.convert("RGB")
        result = detector.detect(img, run_mode=settings.run_mode,
                                 weights_path=settings.weights_path,
                                 device=settings.detector_device, conf=settings.detector_conf)
        if settings.is_real and settings.openvocab_enabled:
            try:
                ov_result = open_vocab.detect_open_vocab(
                    img, weights_path=settings.openvocab_weights,
                    device=settings.detector_device, conf=settings.openvocab_conf)
            except detector.DetectorUnavailable as exc:
                return _fail_job(session, job, "MODEL_UNAVAILABLE",
                                 f"open-vocab unavailable: {exc}", retryable=False)
            result.detections = fusion.fuse(result.detections, ov_result.detections,
                                            iou_thr=settings.fusion_iou)
    except detector.DetectorUnavailable as exc:
        return _fail_job(session, job, "MODEL_UNAVAILABLE", str(exc), retryable=False)
    except ApiError as exc:
        return _fail_job(session, job, exc.code, exc.message, retryable=exc.retryable)
    except Exception as exc:  # noqa: BLE001 - worker 边界，落库为 failed
        return _fail_job(session, job, "INTERNAL", f"detection error: {exc}", retryable=True)

    _persist_detections(session, job, result)
    job.status = "succeeded"
    job.stage = "detecting"
    job.result_json = json.dumps({
        "model_name": result.model_name,
        "model_version": result.model_version,
        "run_mode": result.run_mode,
        "device": result.device,
        "elapsed_seconds": round(result.elapsed_seconds, 4),
        "image_width": result.image_width,
        "image_height": result.image_height,
        "count": len(result.detections),
        "open_vocab": ({"model_name": ov_result.model_name,
                        "model_version": ov_result.model_version,
                        "raw_count": len(ov_result.detections)} if ov_result else None),
        "fusion_iou": settings.fusion_iou if ov_result else None,
    })
    session.commit()
    return job


def _fail_job(session: Session, job: Job, code: str, message: str, retryable: bool) -> Job:
    job.status = "failed"
    job.error_json = json.dumps({"code": code, "message": message, "retryable": retryable})
    session.commit()
    return job


def _persist_detections(session: Session, job: Job, result: detector.DetectionResult) -> None:
    # object_id 守恒（H01）：每个检测框生成一次稳定 id，不重复写入。
    session.query(Detection).filter(Detection.job_id == job.id).delete()
    for det in result.detections:
        session.add(Detection(
            id=uuid.uuid4().hex, job_id=job.id, class_id=det.class_id,
            class_name=det.class_name, confidence=det.confidence,
            bbox_image=json.dumps([round(v, 6) for v in det.bbox_image]),
            source=det.source,
            raw_class_name=getattr(det, "raw_class_name", "") or None,
        ))


# ---------------------------------------------------------------- 理解任务（interpret）

def create_interpret_job(session: Session, project_id: str, request: dict) -> Job:
    """创建 interpret 任务：把入参快照存入 request_json，后台跑确定性 facts + 模板 NL。

    物品来源二选一：显式 objects 或 detect_job_id（须属同一项目）。
    """
    get_project(session, project_id)
    objects = request.get("objects")
    detect_job_id = request.get("detect_job_id")
    if not objects and not detect_job_id:
        raise ApiError("INVALID_REQUEST", "interpret requires objects or detect_job_id", status_code=400)
    if detect_job_id:
        src = session.get(Job, detect_job_id)
        if src is None or src.project_id != project_id:
            raise ApiError("JOB_NOT_FOUND", f"detect job not found in project: {detect_job_id}", status_code=404)
    job = Job(id=uuid.uuid4().hex, project_id=project_id, type="interpret",
              status="queued", stage="interpreting", attempt=1,
              request_json=json.dumps(request))
    session.add(job)
    session.commit()
    return job


def _scene_objects_from_request(session: Session, request: dict) -> List[dict]:
    """把请求（显式 objects 或 detect_job 的持久化检测）归一为原始物品条目（bbox_image）。"""
    items: List[dict] = []
    if request.get("objects"):
        for i, o in enumerate(request["objects"]):
            items.append({
                "object_id": o.get("object_id") or f"obj_{i}",
                "class_name": o["class_name"],
                "bbox_image": list(o["bbox_image"]),
                "fixed": bool(o.get("fixed", False)),
                "high_frequency": bool(o.get("high_frequency", False)),
                "source": o.get("source") or "",
            })
        return items
    detect_job_id = request["detect_job_id"]
    dets = session.query(Detection).filter(Detection.job_id == detect_job_id).all()
    for d in dets:
        items.append({
            "object_id": d.id, "class_name": d.class_name,
            "bbox_image": json.loads(d.bbox_image),
            "fixed": False, "high_frequency": False, "source": d.source or "",
        })
    return items


def _load_interpret_image(session: Session, request: dict, project_id: str | None = None):
    """加载 interpret 关联原图（用于确定性颜色属性）。

    仅 detect_job 路径能取到 image_asset（该检测任务上传的原图）；显式 objects
    路径未关联原图 → 返回 None（颜色 unknown，不编造；几何仍可算）。原图不可读时
    同样降级为 None（颜色为 best-effort 属性，不阻断 interpret 的几何事实与 NL）。

    纵深防御（约定7）：传入 project_id 时，所取 asset 必须归属同一项目，否则降级
    为 None（跨项目资源不得被读取；即使未来 request 扩展 image_asset_id 也不泄露）。
    """
    detect_job_id = request.get("detect_job_id")
    image_asset_id = request.get("image_asset_id")
    if not image_asset_id and detect_job_id:
        src = session.get(Job, detect_job_id)
        # 纵深防御：detect job 必须归属同一项目（与 create_interpret_job 校验一致）
        if src is not None and (project_id is None or src.project_id == project_id):
            image_asset_id = src.image_asset_id
    if not image_asset_id:
        return None
    asset = session.get(Asset, image_asset_id)
    if asset is None:
        return None
    if project_id is not None and asset.project_id != project_id:
        return None  # 跨项目 asset → 不读取（降级颜色 unknown）
    try:
        with Image.open(asset.path) as im:
            im.load()
            return im.convert("RGB")
    except Exception:  # noqa: BLE001 - 原图不可读 → 颜色降级 unknown，不阻断 interpret
        return None


def process_interpret_job(session: Session, settings: Settings, job_id: str) -> Job:
    """worker 执行 interpret：确定性几何事实 + 模板中文描述（不调用 VL，B 阶段 blocked）。

    坐标：bbox_image --(desk_bbox_image)--> bbox_desk 由后端推导（约定3）。
    非法坐标/类别 → failed，不静默修正（FR02/FR06）。
    """
    job = session.get(Job, job_id)
    if job is None:
        raise ApiError("JOB_NOT_FOUND", f"job not found: {job_id}", status_code=404)
    if job.status in ("succeeded", "failed", "cancelled"):
        return job

    job.status = "running"
    job.stage = "interpreting"
    session.commit()

    try:
        request = json.loads(job.request_json or "{}")
        desk_provided = bool(request.get("desk_bbox_image"))
        desk = request.get("desk_bbox_image") or [0.0, 0.0, 1.0, 1.0]
        raw_items = _scene_objects_from_request(session, request)
        image = _load_interpret_image(session, request, job.project_id)  # 关联原图（颜色属性）；无则 None→颜色 unknown
        scene_objs: List[SceneObject] = []
        for it in raw_items:
            bbox_desk = derive_bbox_desk(it["bbox_image"], desk)  # 约定3：后端推导
            scene_objs.append(SceneObject(
                object_id=it["object_id"], class_name=it["class_name"],
                bbox_desk=bbox_desk, fixed=it["fixed"],
                high_frequency=it["high_frequency"], source=it["source"],
                bbox_image=it["bbox_image"]))
        facts = scene_facts.compute_scene_facts(
            scene_objs, user_side=request.get("user_side", "bottom"),
            handedness=request.get("handedness", "right"), mode=request.get("mode", "office"),
            image=image)
        description = render_nl.render(facts)
    except SceneFactsError as exc:
        return _fail_job(session, job, exc.code, exc.message, retryable=False)
    except ApiError as exc:
        return _fail_job(session, job, exc.code, exc.message, retryable=exc.retryable)
    except Exception as exc:  # noqa: BLE001 - worker 边界，落库为 failed
        return _fail_job(session, job, "INTERNAL", f"interpret error: {exc}", retryable=True)

    job.status = "succeeded"
    job.stage = "interpreting"
    job.result_json = json.dumps({
        "count": len(scene_objs),
        # 回写事实推导基准（约定3 可追溯）：所用桌面矩形与“全图当桌面”假设标记
        "desk_bbox_image": desk,
        "desk_assumed_full_image": not desk_provided,
        "scene_facts": facts,
        "description": description,
        "vl": {"enabled": False, "reason": "B-stage blocked"},  # VL 增强未接入，如实标注
    }, ensure_ascii=False)
    session.commit()
    return job


# ---------------------------------------------------------------- 查询装配

def job_to_dict(session: Session, job: Job) -> dict:
    dets = session.query(Detection).filter(Detection.job_id == job.id).all()
    error = json.loads(job.error_json) if job.error_json else None
    return {
        "id": job.id,
        "project_id": job.project_id,
        "type": job.type,
        "status": job.status,
        "stage": job.stage,
        "attempt": job.attempt,
        "result": json.loads(job.result_json) if job.result_json else None,
        "detections": [
            {"id": d.id, "class_id": d.class_id, "class_name": d.class_name,
             "confidence": d.confidence, "bbox_image": json.loads(d.bbox_image),
             "source": d.source, "raw_class_name": d.raw_class_name}
            for d in dets
        ],
        "error": error,
        "created_at": _now_iso(job.created_at),
        "updated_at": _now_iso(job.updated_at),
    }


def get_job(session: Session, job_id: str) -> Job:
    job = session.get(Job, job_id)
    if job is None:
        raise ApiError("JOB_NOT_FOUND", f"job not found: {job_id}", status_code=404)
    return job


def derive_bbox_desk(bbox_image: List[float], desk_bbox_image: List[float]) -> List[float]:
    """后端从原图框与桌面范围推导桌面框（约定3）。非法坐标转 ApiError。"""
    try:
        return image_to_desk(bbox_image, desk_bbox_image)
    except CoordinateError as exc:
        raise ApiError(exc.code, exc.message, status_code=422)
