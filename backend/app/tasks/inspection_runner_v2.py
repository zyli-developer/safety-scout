"""v2 BackgroundTasks 入口 —— 与 inspection_runner.py 平行。

为什么 v2 单开 runner：v1 runner 签名带 LLMProvider，v2 不用；
SkillLoader 由调用方注入（不在 runner 里自建，便于集成测 override）。
"""
from __future__ import annotations

import logging

from app.config import get_settings
from app.safety_agent.loader import SkillLoader
from app.services.inspection_v2 import run_inspection_v2
from app.storage.db import connect

logger = logging.getLogger(__name__)


async def run(
    inspection_id: str,
    image: bytes,
    skill_loader: SkillLoader,
) -> None:
    """BackgroundTasks 调度的 v2 entry。失败也不上抛（FastAPI 拿不到结果）。"""
    settings = get_settings()
    conn = connect(settings.sqlite_path)
    try:
        await run_inspection_v2(
            inspection_id=inspection_id,
            image=image,
            conn=conn,
            settings=settings,
            skill_loader=skill_loader,
        )
    finally:
        conn.close()
