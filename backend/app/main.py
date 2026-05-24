"""FastAPI 应用入口（Phase 2 Task 6）。

本版做：
- 创建 FastAPI app
- 挂 routers
- 注册 SafetyScoutError → JSON envelope 全局 handler（架构 §2.4）
- lifespan 顺序：setup_logging → init_schema → orphan recovery（架构 §2.6）
- 顶部强制 Windows ProactorEventLoop（asyncio.create_subprocess_exec 需要它，
  否则 uvicorn --reload 在 Windows 上默认 SelectorEventLoop，
  ClaudeCLIProvider 跑子进程会 NotImplementedError）
"""
from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

# 必须在 FastAPI / 任何 await 之前设 policy。uvicorn --reload 在 Windows 上
# 默认走 SelectorEventLoop，不支持 asyncio.create_subprocess_exec，导致
# ClaudeCLIProvider.analyze() 抛 NotImplementedError。
# 见 https://docs.python.org/3/library/asyncio-platforms.html#windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException as FastAPIHTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.errors import RateLimitedError, SafetyScoutError
from app.logging_config import setup_logging
from app.rate_limit import limiter
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
    # 启动总览：生产排查第一步看这条 —— 一眼确认挂的是哪个 provider / 模型 /
    # 数据目录 / 限流值。所有敏感字段（doubao_api_key）按 mask 处理。
    logger.info(
        "safety-scout backend starting",
        extra={
            "llm_provider": settings.llm_provider,
            "claude_model": settings.claude_model,
            "claude_timeout_s": settings.claude_timeout_seconds,
            "doubao_model": settings.doubao_model,
            "doubao_api_key_set": bool(settings.doubao_api_key),
            "sqlite_path": settings.sqlite_path,
            "upload_dir": settings.upload_dir,
            "max_image_mb": settings.max_image_mb,
            "rate_limit_per_minute": settings.rate_limit_per_minute,
            "backend_hard_timeout_s": settings.backend_hard_timeout_s,
        },
    )

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

    logger.info("safety-scout backend ready")
    yield
    logger.info("safety-scout backend shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Safety Scout",
        version="0.2.0",
        lifespan=lifespan,
    )

    # slowapi 需要找到 limiter 实例；同时 routes 用同一个实例做装饰器。
    app.state.limiter = limiter

    # CORS：MVP 阶段 dev 跨源请求（H5 在 127.0.0.1:RANDOM、backend 在 localhost:8000）。
    # Taro 4 H5 的 uploadFile / request polyfill 默认 withCredentials=true（fetch
    # credentials:'include'），所以不能用 allow_origins=["*"]（CORS 规范禁止 *
    # 与 credentials 共存）。改用 regex 匹配本地两个 host + 任意端口、放行 credentials。
    # 生产上线前应把 regex 收紧到具体 web 前端域名 / 小程序 origin（小程序场景一般无 CORS）。
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(SafetyScoutError)
    async def _safety_handler(
        request: Request, exc: SafetyScoutError
    ) -> JSONResponse:
        # 架构 §2.4：所有 SafetyScoutError 子类统一映射成
        # {"error":{code, message, user_message}}，http_status 由子类 ClassVar 决定。
        # 5xx 走 error 级别（需要立刻关注）、4xx 走 warning（业务校验失败，正常流量）。
        log = logging.getLogger("app.main.errors")
        log_method = log.error if exc.http_status >= 500 else log.warning
        log_method(
            "request rejected by SafetyScoutError",
            extra={
                "error_code": exc.code,
                "http_status": exc.http_status,
                "path": request.url.path,
                "method": request.method,
                "client_ip": request.client.host if request.client else None,
                "detail": str(exc),
            },
        )
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

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limit_handler(
        request: Request, exc: RateLimitExceeded
    ) -> JSONResponse:
        # slowapi 抛 RateLimitExceeded —— 强制套上和 SafetyScoutError 一致的
        # error envelope，避免前端见到两种 4xx shape。code/user_message 与
        # errors.RateLimitedError 同步。
        logging.getLogger("app.main.errors").warning(
            "rate limit exceeded",
            extra={
                "error_code": RateLimitedError.code,
                "path": request.url.path,
                "method": request.method,
                "client_ip": request.client.host if request.client else None,
                "limit": str(exc.detail),
            },
        )
        return JSONResponse(
            status_code=RateLimitedError.http_status,
            content={
                "error": {
                    "code": RateLimitedError.code,
                    "message": f"rate limit exceeded: {exc.detail}",
                    "user_message": RateLimitedError.user_message,
                }
            },
        )

    @app.exception_handler(FastAPIHTTPException)
    async def _http_exception_handler(
        request: Request, exc: FastAPIHTTPException
    ) -> JSONResponse:
        # 我们的路由约定：HTTPException 抛出时 detail = {"error": {...}}（见
        # routes/inspections.py 的 404 路径）。把那个 detail 直接当响应 body，
        # 让前端只解一种 shape {"error":{code,message,user_message}}，
        # 不必再 fallback body.detail.error。
        # 兼容 detail 是 str 的极端 fallback（FastAPI 默认 404 等），包成最小 error 包。
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            body: dict[str, object] = exc.detail
        else:
            body = {
                "error": {
                    "code": "HTTP_ERROR",
                    "message": str(exc.detail),
                    "user_message": "请求出错，请稍后重试",
                }
            }
        return JSONResponse(status_code=exc.status_code, content=body)

    app.include_router(health.router)
    app.include_router(inspections.router)
    return app


app = create_app()
