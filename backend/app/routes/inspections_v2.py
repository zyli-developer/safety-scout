"""v2 路由 —— POST /api/v2/analyze + GET /api/v2/inspections/{id}。

与 v1 routes/inspections.py 平行：
- POST 走相同的 image_service.validate → save 流程；create 时打 schema_version='v2'
- BackgroundTasks 调 inspection_runner_v2.run（注入 SkillLoader 单例）
- GET 复用同一张 inspections 表，按 schema_version='v2' 反序列化为 ReportV2Payload

为什么 POST 用 `/analyze` 而 GET 用 `/inspections/{id}`：
- 文档（改造计划 §2.3）明确把 v2 POST 命名为 analyze
- 但保留与 v1 一致的 GET 资源风格，前端轮询逻辑 1:1 可复用
"""
from __future__ import annotations

import json
import sqlite3

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Request,
    UploadFile,
)

from app.config import Settings, get_settings
from app.dependencies import get_db, get_skill_loader
from app.rate_limit import limiter
from app.safety_agent.loader import SkillLoader
from app.schemas.inspection import ErrorBody
from app.schemas.inspection_v2 import (
    CreateInspectionV2Response,
    GetInspectionV2Response,
)
from app.schemas.report_v2 import ReportV2Payload
from app.services import image as image_service
from app.storage import inspection_repo as repo
from app.tasks import inspection_runner_v2

router = APIRouter(prefix="/api/v2", tags=["inspections-v2"])


@router.post(
    "/analyze",
    response_model=CreateInspectionV2Response,
    status_code=202,
)
@limiter.limit("10/minute")
async def create_inspection_v2(
    request: Request,
    background_tasks: BackgroundTasks,
    image: UploadFile = File(...),
    conn: sqlite3.Connection = Depends(get_db),
    skill_loader: SkillLoader = Depends(get_skill_loader),
    settings: Settings = Depends(get_settings),
) -> CreateInspectionV2Response:
    image_bytes = await image.read()
    content_type = image.content_type or ""
    image_service.validate(
        content_type=content_type,
        size_bytes=len(image_bytes),
        max_image_mb=settings.max_image_mb,
    )
    image_path = image_service.save(image_bytes, settings.upload_dir, content_type)
    inspection_id = repo.create(conn, str(image_path), schema_version="v2")

    background_tasks.add_task(
        inspection_runner_v2.run, inspection_id, image_bytes, skill_loader
    )

    return CreateInspectionV2Response(
        inspection_id=inspection_id,
        poll_url=f"/api/v2/inspections/{inspection_id}",
        poll_interval_ms=settings.poll_interval_ms,
        # v2 单次分析比 v1 慢（多轮 tool 调用），前端轮询总时限放宽到 6 min
        timeout_ms=max(settings.timeout_ms, settings.agent_timeout_seconds * 1000 + 30_000),
    )


@router.get(
    "/inspections/{inspection_id}",
    response_model=GetInspectionV2Response,
)
async def get_inspection_v2(
    inspection_id: str,
    conn: sqlite3.Connection = Depends(get_db),
) -> GetInspectionV2Response:
    row = repo.get(conn, inspection_id)
    if row is None or row.schema_version != "v2":
        # v1 行从 v2 GET 拿不到 —— 强制路径隔离，避免前端误把 v1 hazards 当 v2 findings 渲染
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

    report: ReportV2Payload | None = None
    if row.report_json:
        report = ReportV2Payload.model_validate_json(row.report_json)

    error: ErrorBody | None = None
    if row.error_json:
        err_dict = json.loads(row.error_json)
        error = ErrorBody(**err_dict)

    return GetInspectionV2Response(
        inspection_id=row.id,
        status=row.status,  # type: ignore[arg-type]
        created_at=row.created_at,
        updated_at=row.updated_at,
        report=report,
        error=error,
    )
