"""FastAPI 应用入口（Phase 2 Task 6）。

本版做：
- 创建 FastAPI app
- 挂 routers
- 注册 SafetyScoutError → JSON envelope 全局 handler（架构 §2.4）
- lifespan 顺序：setup_logging → init_schema → orphan recovery（架构 §2.6）
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.errors import SafetyScoutError
from app.logging_config import setup_logging
from app.routes import health, inspections
from app.storage import inspection_repo
from app.storage.db import connect, init_schema
from app.storage.inspection_repo import ErrorPayload


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # 先装 JSON logging，再做后续步骤 —— 这样 init_schema / 孤儿恢复的日志都是结构化的
    setup_logging()
    logger = logging.getLogger(__name__)

    settings = get_settings()
    conn = connect(settings.sqlite_path)
    try:
        init_schema(conn)
        # 架构 §2.6：进程重启时把 queued 孤儿全部标 failed，不重跑。
        orphans = inspection_repo.list_orphaned_queued(conn)
        for orphan in orphans:
            inspection_repo.update_failed(
                conn,
                orphan.id,
                ErrorPayload(
                    code="INTERNAL",
                    message="server restarted",
                    user_message="服务重启导致任务中断，请重试",
                ),
            )
            logger.warning(
                "orphan inspection marked failed",
                extra={"inspection_id": orphan.id, "error_code": "INTERNAL"},
            )
        if orphans:
            logger.info(
                "startup orphan recovery done",
                extra={"orphan_count": len(orphans)},
            )
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
