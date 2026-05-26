"""Inspection 业务编排：把 provider / parser / repo / model_meta 串起来。

状态机（架构 §2.5）：
    queued -> processing -> succeeded
                         \\-> failed
被 BackgroundTasks 调用；调用方负责传一个新鲜的 sqlite 连接，本服务不开/关连接。

并发控制：模块级 asyncio.Semaphore(2)，限制同时调 provider.analyze 的数量
（每次 claude CLI 子进程 ~100MB RSS + 60-260s，2 个并发已是 MVP 安全水位）。
"""
from __future__ import annotations

import asyncio
import logging
import sqlite3
import time

from app.errors import SafetyScoutError
from app.llm.base import LLMProvider
from app.llm.parser import parse_report
from app.llm.prompt import ANALYZE_PROMPT
from app.schemas.report import ModelMeta
from app.storage import inspection_repo as repo
from app.storage.inspection_repo import ErrorPayload

logger = logging.getLogger(__name__)

# 进程级并发上限；Phase 2 brainstorm 拍 2。
# 单测可临时替换：service.set_semaphore_for_tests(asyncio.Semaphore(1))
_provider_semaphore = asyncio.Semaphore(2)


def set_semaphore_for_tests(sem: asyncio.Semaphore) -> None:
    """单测里需要不同 cap 时调；生产代码勿用。"""
    global _provider_semaphore
    _provider_semaphore = sem


async def run_inspection(
    inspection_id: str,
    image: bytes,
    provider: LLMProvider,
    conn: sqlite3.Connection,
) -> None:
    """后台任务体。任何异常 → 标 failed，不再向上抛（背景任务无消费者）。"""
    repo.update_processing(conn, inspection_id)

    t0 = time.monotonic()
    try:
        async with _provider_semaphore:
            raw = await provider.analyze(image, ANALYZE_PROMPT)

        async def reprompt(corrective: str) -> str:
            # 二次纠正不必再竞争信号量（已经在信号量内调过一次）
            # 但为公平，复用同一把锁；rare path，不会显著拖慢
            async with _provider_semaphore:
                r = await provider.analyze(image, corrective)
                return r.content

        report = await parse_report(raw.content, reprompt=reprompt)

        # 用真实 provider / model / latency 覆盖模型自填的 model_meta（实测模型
        # 会写出 latency_ms=3200 这种幻觉值；prompt-poc-notes 已记录，由后端覆盖）。
        meta = ModelMeta(
            provider=provider.name,  # type: ignore[arg-type]
            # provider.name 是 Protocol 的 str；ModelMeta.provider 是
            # Literal["claude_cli","fake"]。运行期一致，mypy 不接受 str→Literal。
            model=raw.model,
            latency_ms=raw.latency_ms,
        )
        # prompt 里给 LLM 的 inspection_id / created_at 是占位符
        # ("00000000-0000-0000-0000-000000000000" / "2026-01-01T00:00:00Z")。
        # 必须用真实的 id + 入库时的 created_at 覆盖，否则前端拿到的是占位符 UUID，
        # 报告页查不到对应照片、报告号显示为 NO.00000000-000。
        row = repo.get(conn, inspection_id)
        real_created_at = row.created_at if row is not None else report.created_at
        report = report.model_copy(
            update={
                "inspection_id": inspection_id,
                "created_at": real_created_at,
                "model_meta": meta,
            }
        )

        repo.update_succeeded(conn, inspection_id, report, meta)
        elapsed = int((time.monotonic() - t0) * 1000)
        logger.info(
            "inspection succeeded",
            extra={
                "inspection_id": inspection_id,
                "latency_ms": elapsed,
                "model": raw.model,
                "cost_usd": raw.provider_payload.get("total_cost_usd"),
            },
        )
    except SafetyScoutError as exc:
        repo.update_failed(
            conn,
            inspection_id,
            ErrorPayload(code=exc.code, message=str(exc), user_message=exc.user_message),
        )
        logger.warning(
            "inspection failed",
            extra={"inspection_id": inspection_id, "error_code": exc.code},
        )
    except Exception as exc:  # noqa: BLE001 —— 后台任务必须吞所有，否则任务静默挂掉
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
            "inspection unexpected error",
            extra={"inspection_id": inspection_id},
        )
