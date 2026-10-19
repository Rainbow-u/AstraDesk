"""FastAPI 应用装配（G0：可启动 API；模式明确；CORS 供前端 dev）。

启动：``uvicorn services.api.app:app --reload``（real 模式设 ``ASTRADESK_RUN_MODE=real``）。
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings, load_settings
from .db import make_engine, make_session
from .errors import register_error_handlers
from .routes import router


class _DB:
    """持有 engine 与 session 工厂，挂在 app.state 上供依赖注入使用。"""

    def __init__(self, engine, session_factory):
        self.engine = engine
        self.Session = session_factory


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    settings.data_root.mkdir(parents=True, exist_ok=True)

    engine = make_engine(settings.db_url)
    session_factory = make_session(engine)

    app = FastAPI(title="AstraDesk API", version="0.1.0")
    app.state.settings = settings
    app.state.db = _DB(engine, session_factory)

    register_error_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()
