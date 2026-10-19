"""统一错误异常与 FastAPI 处理器（PRD 8.3）。"""
from __future__ import annotations

import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .schemas import ErrorBody


class ApiError(Exception):
    """业务错误。status_code 用于 HTTP 状态。"""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        retryable: bool = False,
        details: dict | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable
        self.details = details


def _request_id(request: Request) -> str:
    return request.headers.get("x-request-id") or uuid.uuid4().hex


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError):
        body = ErrorBody(
            code=exc.code,
            message=exc.message,
            details=exc.details,
            retryable=exc.retryable,
            request_id=_request_id(request),
        )
        return JSONResponse(status_code=exc.status_code, content=body.model_dump())

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        body = ErrorBody(
            code="INTERNAL",
            message="internal server error",
            retryable=True,
            request_id=_request_id(request),
        )
        return JSONResponse(status_code=500, content=body.model_dump())
