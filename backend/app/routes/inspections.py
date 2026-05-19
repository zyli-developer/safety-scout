"""POST /api/v1/inspections + GET /api/v1/inspections/{id}。

POST：
- 校验 MIME / size（image_service.validate）—— 失败抛 SafetyScoutError，
  让全局 handler 转 4xx envelope；路由本身不做 try/except。
- 落盘（image_service.save）
- repo.create → status=queued
- BackgroundTasks.add_task(inspection_runner.run, ...)
- 立即返 202 + CreateInspectionResponse

GET：
- repo.get → 包成 GetInspectionResponse（report_json / error_json 反序列化）
- 不存在 → 404（用 HTTPException；全局 handler 只接 SafetyScoutError 家族）
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
from app.dependencies import get_db, get_llm_provider
from app.llm.base import LLMProvider
from app.rate_limit import limiter
from app.schemas.inspection import (
    CreateInspectionResponse,
    ErrorBody,
    GetInspectionResponse,
)
from app.schemas.report import ReportPayload
from app.services import image as image_service
from app.storage import inspection_repo as repo
from app.tasks import inspection_runner

router = APIRouter(prefix="/api/v1", tags=["inspections"])


@router.post(
    "/inspections",
    response_model=CreateInspectionResponse,
    status_code=202,
)
# 限速值与 Settings.rate_limit_per_minute=10 对齐；slowapi 不接受 Settings 实例，
# 这里用字面字符串；若 Settings 改了，记得同步本处 + .env.example。
@limiter.limit("10/minute")
async def create_inspection(
    # slowapi 要求装饰器装的路由首参是 request: Request（它从 request 抽 IP 做 key）。
    request: Request,
    background_tasks: BackgroundTasks,
    image: UploadFile = File(...),
    conn: sqlite3.Connection = Depends(get_db),
    provider: LLMProvider = Depends(get_llm_provider),
    settings: Settings = Depends(get_settings),
) -> CreateInspectionResponse:
    # UploadFile 是异步流；一次性读进内存（已通过 max_image_mb 间接限流）。
    image_bytes = await image.read()
    content_type = image.content_type or ""
    image_service.validate(
        content_type=content_type,
        size_bytes=len(image_bytes),
        max_image_mb=settings.max_image_mb,
    )
    image_path = image_service.save(image_bytes, settings.upload_dir, content_type)
    inspection_id = repo.create(conn, str(image_path))

    # BackgroundTasks 自己开 sqlite 连接（见 inspection_runner.run 注释）。
    # 注意：必须传已读 image_bytes，UploadFile 句柄在响应返回后会被关。
    background_tasks.add_task(
        inspection_runner.run, inspection_id, image_bytes, provider
    )

    return CreateInspectionResponse(
        inspection_id=inspection_id,
        poll_url=f"/api/v1/inspections/{inspection_id}",
        poll_interval_ms=settings.poll_interval_ms,
        timeout_ms=settings.timeout_ms,
    )


@router.get(
    "/inspections/{inspection_id}",
    response_model=GetInspectionResponse,
)
async def get_inspection(
    inspection_id: str,
    conn: sqlite3.Connection = Depends(get_db),
) -> GetInspectionResponse:
    row = repo.get(conn, inspection_id)
    if row is None:
        # HTTPException 走 FastAPI 自己的 handler；detail 保留与 SafetyScoutError
        # 一致的 envelope 形态，让前端只解析一种错误结构。
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": "inspection not found",
                    "user_message": "找不到该次检查记录",
                }
            },
        )

    report: ReportPayload | None = None
    if row.report_json:
        report = ReportPayload.model_validate_json(row.report_json)

    error: ErrorBody | None = None
    if row.error_json:
        err_dict = json.loads(row.error_json)
        error = ErrorBody(**err_dict)

    return GetInspectionResponse(
        inspection_id=row.id,
        # repo.InspectionRow.status 是 str（避免 sqlite Row → dataclass 强转）；
        # 这里到 API 边界再收紧为 Literal —— DB 中只可能写入 4 个值，运行期一致。
        status=row.status,  # type: ignore[arg-type]
        created_at=row.created_at,
        updated_at=row.updated_at,
        report=report,
        error=error,
    )
