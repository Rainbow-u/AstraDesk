"""SQLite 持久化模型（PRD 8.2 核心对象子集，T02 桌面识别所需）。"""
from __future__ import annotations

import datetime as _dt
import json

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()


def _utcnow() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


class Project(Base):
    __tablename__ = "projects"
    id = Column(String, primary_key=True)
    title = Column(String, nullable=False, default="未命名项目")
    created_at = Column(DateTime, default=_utcnow)
    deleted_at = Column(DateTime, nullable=True)

    assets = relationship("Asset", back_populates="project")
    jobs = relationship("Job", back_populates="project")


class Asset(Base):
    __tablename__ = "assets"
    id = Column(String, primary_key=True)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    kind = Column(String, nullable=False)  # original / canonical / thumbnail
    path = Column(String, nullable=False)  # 服务端生成的相对路径
    sha256 = Column(String, nullable=False)
    width = Column(Integer, nullable=False)
    height = Column(Integer, nullable=False)

    project = relationship("Project", back_populates="assets")


class Job(Base):
    __tablename__ = "jobs"
    id = Column(String, primary_key=True)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    type = Column(String, nullable=False)  # detect / plan / generate
    status = Column(String, nullable=False, default="queued")
    stage = Column(String, nullable=True)
    attempt = Column(Integer, nullable=False, default=1)
    image_asset_id = Column(String, nullable=True)
    request_json = Column(Text, nullable=True)  # 异步任务入参快照(如 interpret 的桌面框/偏好)
    result_json = Column(Text, nullable=True)
    error_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    project = relationship("Project", back_populates="jobs")
    detections = relationship("Detection", back_populates="job")


class Detection(Base):
    __tablename__ = "detections"
    id = Column(String, primary_key=True)
    job_id = Column(String, ForeignKey("jobs.id"), nullable=False)
    class_id = Column(Integer, nullable=False)
    class_name = Column(String, nullable=False)
    confidence = Column(Float, nullable=False)
    bbox_image = Column(Text, nullable=False)  # JSON [x1,y1,x2,y2] 归一化
    source = Column(String, nullable=True)  # 检测来源(yolov10:*/yolo-world/manual/mock)
    raw_class_name = Column(String, nullable=True)  # 开放词表映射前原始提示词名(FR03 原始类可追溯)

    job = relationship("Job", back_populates="detections")

    @property
    def bbox(self) -> list:
        return json.loads(self.bbox_image)


def make_engine(db_url: str = "sqlite:///data/astradesk.db"):
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    _migrate(engine)
    return engine


def _migrate(engine):
    """幂等轻量迁移：为旧库补列（create_all 不改已有表）。"""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    tables = set(insp.get_table_names())
    if "detections" in tables:
        cols = {c["name"] for c in insp.get_columns("detections")}
        if "source" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE detections ADD COLUMN source VARCHAR"))
        if "raw_class_name" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE detections ADD COLUMN raw_class_name VARCHAR"))
    if "jobs" in tables:
        cols = {c["name"] for c in insp.get_columns("jobs")}
        if "request_json" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE jobs ADD COLUMN request_json TEXT"))


def make_session(engine):
    return sessionmaker(bind=engine, expire_on_commit=False)
