"""v2 反馈路由 —— POST /api/v2/inspections/{id}/feedback。

只挂在 v2 路径下：v1 没有 check_id 概念，反馈语义对不上。
对应 docs/specs/v2-rollout.md §二（Badcase 闭环）。

错误形状：与 inspections_v2 一致 —— 404 detail = {"error":{code,message,user_message}}，
全局 _http_exception_handler 会把 detail 直接当 response body 返。
"""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request

from app.dependencies import get_db
from app.rate_limit import limiter
from app.schemas.feedback import FeedbackCreate, FeedbackCreateResponse
from app.storage import feedback_repo, inspection_repo

router = APIRouter(prefix="/api/v2", tags=["feedback-v2"])


@router.post(
    "/inspections/{inspection_id}/feedback",
    response_model=FeedbackCreateResponse,
    status_code=201,
)
@limiter.limit("30/minute")
async def create_feedback(
    request: Request,
    inspection_id: str,
    body: FeedbackCreate,
    conn: sqlite3.Connection = Depends(get_db),
) -> FeedbackCreateResponse:
    """落一条反馈。要求 inspection 存在且属于 v2 路径。"""
    row = inspection_repo.get(conn, inspection_id)
    if row is None or row.schema_version != "v2":
        # 与 inspections_v2.get_inspection_v2 的 404 文案对齐
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": "v2 inspection not found",
                    "user_message": "找不到该次检查记录",
                }
            },
        )

    saved = feedback_repo.create(
        conn,
        inspection_id=inspection_id,
        kind=body.kind,
        check_id=body.check_id,
        description=body.description,
    )
    return FeedbackCreateResponse(
        feedback_id=saved.id,
        inspection_id=saved.inspection_id,
        created_at=saved.created_at,
    )
