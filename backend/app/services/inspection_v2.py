"""v2 Inspection 业务编排 —— 与 v1 services/inspection.py 平行但路径分离。

状态机沿用 v1（queued → processing → succeeded|failed）；唯一不同：
- v2 调 safety_agent.agent.analyze_image，不走 ClaudeCLIProvider
- 报告写入用 repo.update_succeeded_v2（schema_version='v2' 是 create 时定的，
  succeeded_v2 不再回写该列）
- model_meta_json 是 v2 自定义结构：包含 token / tool_calls / scenarios / cost

并发：另开一把信号量，与 v1 隔离 —— v1 跑 CLI 子进程 RAM 占用大、v2 走
SDK 短连接相对轻，理论上可以同时跑；分开 cap 也便于 future 调优。
"""
from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time

from app.config import Settings
from app.errors import SafetyScoutError
from app.safety_agent.agent import analyze_image
from app.safety_agent.loader import SkillLoader
from app.storage import inspection_repo as repo
from app.storage.inspection_repo import ErrorPayload

logger = logging.getLogger(__name__)

# v2 走 SDK + 本地 Claude CLI（每次单独 spawn），并发上限给 2，与 v1 同档。
# 单测可临时替换 sem
_v2_semaphore = asyncio.Semaphore(2)


def set_v2_semaphore_for_tests(sem: asyncio.Semaphore) -> None:
    global _v2_semaphore
    _v2_semaphore = sem


async def run_inspection_v2(
    inspection_id: str,
    image: bytes,
    conn: sqlite3.Connection,
    settings: Settings,
    skill_loader: SkillLoader,
) -> None:
    """v2 后台任务。任何异常 → 标 failed。"""
    repo.update_processing(conn, inspection_id)

    t0 = time.monotonic()
    try:
        async with _v2_semaphore:
            report, stats = await analyze_image(
                image_bytes=image,
                settings=settings,
                skill_loader=skill_loader,
            )

        meta_json = json.dumps(
            {
                "provider": "claude_agent_sdk",
                "model": settings.agent_model,
                "elapsed_ms": stats.elapsed_ms,
                "tool_calls": stats.tool_calls,
                "scenarios_loaded": stats.scenarios_loaded,
                "input_tokens": stats.input_tokens,
                "output_tokens": stats.output_tokens,
                "cost_usd": stats.cost_usd,
            },
            ensure_ascii=False,
        )
        repo.update_succeeded_v2(conn, inspection_id, report, meta_json)
        elapsed = int((time.monotonic() - t0) * 1000)
        logger.info(
            "v2 inspection succeeded",
            extra={
                "inspection_id": inspection_id,
                "latency_ms": elapsed,
                "model": settings.agent_model,
                "tool_calls": stats.tool_calls,
                "scenarios": stats.scenarios_loaded,
                "findings": len(report.findings),
                "input_tokens": stats.input_tokens,
                "output_tokens": stats.output_tokens,
                "cost_usd": stats.cost_usd,
            },
        )
    except SafetyScoutError as exc:
        repo.update_failed(
            conn,
            inspection_id,
            ErrorPayload(code=exc.code, message=str(exc), user_message=exc.user_message),
        )
        logger.warning(
            "v2 inspection failed",
            extra={"inspection_id": inspection_id, "error_code": exc.code},
        )
    except Exception as exc:  # noqa: BLE001 —— 后台任务必须吞所有
        repo.update_failed(
            conn,
            inspection_id,
            ErrorPayload(
                code="INTERNAL",
                message=f"{type(exc).__name__}: {exc}",
                user_message="服务内部错误，请重试",
            ),
        )
        logger.exception(
            "v2 inspection unexpected error",
            extra={"inspection_id": inspection_id},
        )
