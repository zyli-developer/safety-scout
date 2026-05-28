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
import hashlib
import json
import logging
import sqlite3
import time

from app.config import Settings
from app.errors import LLMTimeoutError, SafetyScoutError
from app.safety_agent.agent import analyze_image
from app.safety_agent.loader import SkillLoader
from app.storage import inspection_repo as repo
from app.storage import metrics_repo
from app.storage.inspection_repo import ErrorPayload
from app.storage.metrics_repo import (
    InputFingerprint,
    RuntimeMetrics,
    VersionFingerprint,
)

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

    # 质量追踪指纹：在跑分析之前就准备好，无论成功失败都要写 metrics（防幸存者偏差）
    image_sha = hashlib.sha256(image).hexdigest()
    version_fp = VersionFingerprint(
        api_version="v2",
        prompt_version=skill_loader.index_version,  # v2 prompt 由 skill 库版本决定
        skill_index_version=skill_loader.index_version,
        model=settings.agent_model,
    )
    input_fp = InputFingerprint(image_sha256=image_sha, image_bytes=len(image))

    t0 = time.monotonic()
    try:
        async with _v2_semaphore:
            report, stats = await analyze_image(
                image_bytes=image,
                settings=settings,
                skill_loader=skill_loader,
            )

        # scenarios_loaded：以前从 load_scenario_skill 工具调用累计；该工具已下线
        # （场景内容全部 inline 进 system prompt）。改用 report.report_meta.scene_detected
        # —— 这是模型经过分析后判定"图片实际命中"的场景 ID 列表，语义比"模型加载了
        # 哪些清单"更准（旧字段其实就是模型自己挑的命中场景，差别仅在采集时机）。
        scene_detected = list(report.report_meta.scene_detected or [])

        meta_json = json.dumps(
            {
                "provider": "claude_agent_sdk",
                "model": settings.agent_model,
                "elapsed_ms": stats.elapsed_ms,
                "tool_calls": stats.tool_calls,
                "scenarios_loaded": scene_detected,
                "input_tokens": stats.input_tokens,
                "output_tokens": stats.output_tokens,
                "cache_read_tokens": stats.cache_read_tokens,
                "cache_creation_tokens": stats.cache_creation_tokens,
                "cost_usd": stats.cost_usd,
                "tool_call_timings": stats.tool_call_timings,
            },
            ensure_ascii=False,
        )
        repo.update_succeeded_v2(conn, inspection_id, report, meta_json)
        elapsed = int((time.monotonic() - t0) * 1000)
        # 写质量追踪指标（成功路径）
        metrics_repo.record_from_report(
            conn,
            inspection_id,
            version=version_fp,
            inp=input_fp,
            runtime=RuntimeMetrics(
                total_elapsed_ms=elapsed,
                input_tokens=stats.input_tokens,
                output_tokens=stats.output_tokens,
                cache_read_tokens=stats.cache_read_tokens,
                cache_creation_tokens=stats.cache_creation_tokens,
                cost_usd=stats.cost_usd,
                tool_calls=stats.tool_calls,
                scenarios_loaded=scene_detected,
                tool_call_timings=stats.tool_call_timings,
            ),
            report=report,
            status="succeeded",
        )
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
                "cache_read_tokens": stats.cache_read_tokens,
                "cache_creation_tokens": stats.cache_creation_tokens,
                "cost_usd": stats.cost_usd,
            },
        )
    except SafetyScoutError as exc:
        repo.update_failed(
            conn,
            inspection_id,
            ErrorPayload(code=exc.code, message=str(exc), user_message=exc.user_message),
        )
        elapsed = int((time.monotonic() - t0) * 1000)
        metrics_repo.record_failure(
            conn,
            inspection_id,
            version=version_fp,
            inp=input_fp,
            runtime=RuntimeMetrics(total_elapsed_ms=elapsed),
            status="timeout" if isinstance(exc, LLMTimeoutError) else "failed",
            error_code=exc.code,
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
        elapsed = int((time.monotonic() - t0) * 1000)
        metrics_repo.record_failure(
            conn,
            inspection_id,
            version=version_fp,
            inp=input_fp,
            runtime=RuntimeMetrics(total_elapsed_ms=elapsed),
            status="failed",
            error_code="INTERNAL",
        )
        logger.exception(
            "v2 inspection unexpected error",
            extra={"inspection_id": inspection_id},
        )
