"""FastAPI 路由（AGENTS.md：路由只做协议处理，业务在 service）。

统一前缀 ``/api/v1``；异步检测任务返回 202 + job，后台执行；查询返回状态与结果。
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, Request, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from packages.vision import detector

from . import service
from .config import Settings
from .errors import ApiError
from .schemas import (
    CapabilitiesOut,
    DetectJobIn,
    DetectorCapability,
    ImageUploadOut,
    InterpretJobIn,
    JobOut,
    ProjectCreateIn,
    ProjectOut,
)

router = APIRouter(prefix="/api/v1")


def get_session(request: Request):
    db = request.app.state.db
    session = db.Session()
    try:
        yield session
    finally:
        session.close()


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


# ---------------------------------------------------------------- 健康与能力

@router.get("/health")
def health(settings: Settings = Depends(get_settings)) -> dict:
    return {"status": "ok", "run_mode": settings.run_mode}


@router.get("/capabilities", response_model=CapabilitiesOut)
def capabilities(settings: Settings = Depends(get_settings)) -> CapabilitiesOut:
    if settings.is_real:
        try:
            detector._load_model(settings.weights_path)
            available, name, version = True, settings.weights_path.stem, settings.weights_path.name
        except detector.DetectorUnavailable as exc:
            available, name, version = False, settings.weights_path.stem, f"unavailable: {exc}"
    else:
        available, name, version = True, "mock-detector", "mock-0.1"
    open_vocab = None
    features = ["detect", "interpret"]  # interpret = 确定性 facts + 模板 NL（离线，两模式均可用）
    if settings.is_real:
        ov_available = settings.openvocab_weights.exists()
        open_vocab = {
            "enabled": settings.openvocab_enabled,
            "available": ov_available,
            "model_name": "yolo-world",
            "model_version": settings.openvocab_weights.name,
        }
        # W7：仅在启用且权重实际存在时才 advertise open_vocab 特性；
        # 启用但缺权重会使检测任务 MODEL_UNAVAILABLE（不回退），故不当作可用能力上报。
        if settings.openvocab_enabled and ov_available:
            features.append("open_vocab")
    return CapabilitiesOut(
        run_mode=settings.run_mode,
        detector=DetectorCapability(available=available, model_name=name, model_version=version),
        features=features,
        open_vocab=open_vocab,
    )


# ---------------------------------------------------------------- 项目

@router.post("/projects", response_model=ProjectOut, status_code=201)
def create_project(payload: ProjectCreateIn, session: Session = Depends(get_session)) -> dict:
    proj = service.create_project(session, payload.title or "未命名项目")
    return {"id": proj.id, "title": proj.title,
            "created_at": service._now_iso(proj.created_at), "assets": []}


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(session: Session = Depends(get_session)) -> list:
    out = []
    for p in service.list_projects(session):
        out.append({"id": p.id, "title": p.title,
                    "created_at": service._now_iso(p.created_at), "assets": []})
    return out


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, session: Session = Depends(get_session)) -> dict:
    proj = service.get_project(session, project_id)
    assets = [
        {"id": a.id, "kind": a.kind, "url": f"/api/v1/assets/{a.id}",
         "width": a.width, "height": a.height, "sha256": a.sha256}
        for a in proj.assets
    ]
    return {"id": proj.id, "title": proj.title,
            "created_at": service._now_iso(proj.created_at), "assets": assets}


# ---------------------------------------------------------------- 图像上传

@router.post("/projects/{project_id}/images", response_model=ImageUploadOut)
async def upload_image(project_id: str, file: UploadFile = File(...),
                       session: Session = Depends(get_session),
                       settings: Settings = Depends(get_settings)) -> dict:
    raw = await file.read()
    return service.upload_image(session, settings, project_id, file.filename or "", raw)


@router.get("/assets/{asset_id}")
def get_asset(asset_id: str, session: Session = Depends(get_session)) -> FileResponse:
    asset = service.get_asset(session, asset_id)
    path = Path(asset.path)
    if not path.exists():
        raise ApiError("ASSET_NOT_FOUND", f"asset file missing: {asset_id}", status_code=404)
    media = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return FileResponse(str(path), media_type=media)


# ---------------------------------------------------------------- 检测任务

def _run_detect_job(app, job_id: str) -> None:
    """后台任务：用独立 session 执行检测（请求 session 已关闭）。"""
    db = app.state.db
    session = db.Session()
    try:
        service.process_detect_job(session, app.state.settings, job_id)
    finally:
        session.close()


@router.post("/projects/{project_id}/jobs/detect", response_model=JobOut, status_code=202)
def create_detect_job(project_id: str, payload: DetectJobIn, request: Request,
                      background: BackgroundTasks,
                      session: Session = Depends(get_session)) -> dict:
    job = service.create_detect_job(session, project_id, payload.image_asset_id)
    background.add_task(_run_detect_job, request.app, job.id)
    return service.job_to_dict(session, job)


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, session: Session = Depends(get_session)) -> dict:
    job = service.get_job(session, job_id)
    return service.job_to_dict(session, job)


# ---------------------------------------------------------------- 理解任务（interpret）

def _run_interpret_job(app, job_id: str) -> None:
    """后台任务：用独立 session 执行确定性 facts + 模板 NL。"""
    db = app.state.db
    session = db.Session()
    try:
        service.process_interpret_job(session, app.state.settings, job_id)
    finally:
        session.close()


@router.post("/projects/{project_id}/jobs/interpret", response_model=JobOut, status_code=202)
def create_interpret_job(project_id: str, payload: InterpretJobIn, request: Request,
                         background: BackgroundTasks,
                         session: Session = Depends(get_session)) -> dict:
    job = service.create_interpret_job(session, project_id, payload.model_dump(exclude_none=True))
    background.add_task(_run_interpret_job, request.app, job.id)
    return service.job_to_dict(session, job)
