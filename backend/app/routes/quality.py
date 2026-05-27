"""质量趋势 HTTP API（docs/specs/quality-tracking.md §5.1）。

GET /api/v1/quality/trend?metric=<m>&group_by=<g>&since=<iso>

无认证（与现有 v2 API 一致，dev 阶段）。
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import get_db
from app.services.quality_trend import (
    VALID_GROUP_BYS,
    VALID_METRICS,
    GroupBy,
    Metric,
    trend,
)

router = APIRouter(prefix="/api/v1/quality", tags=["quality"])


@router.get("/trend")
async def get_trend(
    metric: Metric = Query(
        ...,
        description=f"指标名，可选: {', '.join(VALID_METRICS)}",
    ),
    group_by: GroupBy = Query(
        ...,
        description=f"分桶维度，可选: {', '.join(VALID_GROUP_BYS)}",
    ),
    since: str | None = Query(
        None,
        description="起始时间 ISO8601 (如 2026-05-01T00:00:00Z)；默认 30 天前",
    ),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """返回 (group, x, value, n) 序列 —— 给前端 dashboard 折线图用。"""
    try:
        return trend(conn, metric=metric, group_by=group_by, since=since)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "INVALID_PARAM",
                    "message": str(exc),
                    "user_message": "参数错误，请检查 metric / group_by",
                }
            },
        ) from exc
