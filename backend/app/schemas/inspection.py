"""API I/O schemas for /api/v1/inspections。

设计要点：
- POST 立返 202 + CreateInspectionResponse，前端拿 poll_url 轮询。
- GET 用 status 字段判断状态机位置（queued/processing/succeeded/failed），
  succeeded 时 report 非 None；failed 时 error 非 None。
- ErrorBody 与全局 SafetyScoutError handler / repo.ErrorPayload 三处对齐：
  {code, message(dev), user_message(zh)}。
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.schemas.report import ReportPayload


class CreateInspectionResponse(BaseModel):
    """POST /api/v1/inspections 202 响应。"""

    inspection_id: str
    poll_url: str  # e.g., "/api/v1/inspections/{id}"
    poll_interval_ms: int
    timeout_ms: int
    status: Literal["queued"] = "queued"


class ErrorBody(BaseModel):
    code: str
    message: str  # dev-facing
    user_message: str  # zh, 给前端


class InspectionErrorEnvelope(BaseModel):
    error: ErrorBody


class GetInspectionResponse(BaseModel):
    """GET /api/v1/inspections/{id} 响应。

    - status=queued / processing → report 与 error 均 None
    - status=succeeded → report 非 None，error None
    - status=failed → error 非 None，report None
    """

    inspection_id: str
    status: Literal["queued", "processing", "succeeded", "failed"]
    created_at: str
    updated_at: str
    report: ReportPayload | None = None
    error: ErrorBody | None = None
