"""FastAPI 应用入口（Phase 2 Task 5 最小版）。

Task 6 会在此基础上加：
- structured JSON logging 初始化
- startup 期孤儿任务恢复（list_orphaned_queued → 标 failed）
- 更详细的 lifespan 钩子

本版只做：
- 创建 FastAPI app
- 挂 routers
- 注册 SafetyScoutError → JSON envelope 全局 handler（架构 §2.4）
- 启动时 init_schema（建表幂等）
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.errors import SafetyScoutError
from app.routes import health, inspections
from app.storage.db import connect, init_schema


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    conn = connect(settings.sqlite_path)
    try:
        init_schema(conn)
    finally:
        conn.close()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Safety Scout",
        version="0.2.0",
        lifespan=lifespan,
    )

    @app.exception_handler(SafetyScoutError)
    async def _safety_handler(
        request: Request, exc: SafetyScoutError
    ) -> JSONResponse:
        # 架构 §2.4：所有 SafetyScoutError 子类统一映射成
        # {"error":{code, message, user_message}}，http_status 由子类 ClassVar 决定。
        return JSONResponse(
            status_code=exc.http_status,
            content={
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                    "user_message": exc.user_message,
                }
            },
        )

    app.include_router(health.router)
    app.include_router(inspections.router)
    return app


app = create_app()
