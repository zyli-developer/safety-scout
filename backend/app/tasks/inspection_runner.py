"""BackgroundTasks 入口：管理 per-task sqlite 连接生命周期，调 inspection 服务。

为什么 runner 自己开连接：FastAPI 请求级别的 conn（dependencies.get_db）在
background task 启动前就会被关掉；background task 必须有自己独立的 conn。
"""
from __future__ import annotations

import logging

from app.config import get_settings
from app.llm.base import LLMProvider
from app.services.inspection import run_inspection
from app.storage.db import connect

logger = logging.getLogger(__name__)


async def run(
    inspection_id: str,
    image: bytes,
    provider: LLMProvider,
) -> None:
    """BackgroundTasks 调度的 entry。失败也不向上抛（FastAPI 拿不到结果）。"""
    settings = get_settings()
    conn = connect(settings.sqlite_path)
    try:
        await run_inspection(inspection_id, image, provider, conn)
    finally:
        conn.close()
