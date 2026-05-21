"""v2 API I/O schemas —— POST /api/v2/analyze + GET /api/v2/inspections/{id}。

与 v1 schemas/inspection.py 结构一致；区别只在 report 字段类型用 ReportV2Payload。
ErrorBody 直接复用 v1 的（envelope shape 全局统一）。
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.schemas.inspection import ErrorBody
from app.schemas.report_v2 import ReportV2Payload


class CreateInspectionV2Response(BaseModel):
    """POST /api/v2/analyze 202 响应。"""

    inspection_id: str
    poll_url: str  # "/api/v2/inspections/{id}"
    poll_interval_ms: int
    timeout_ms: int
    status: Literal["queued"] = "queued"


class GetInspectionV2Response(BaseModel):
    """GET /api/v2/inspections/{id} 响应。"""

    inspection_id: str
    status: Literal["queued", "processing", "succeeded", "failed"]
    created_at: str
    updated_at: str
    report: ReportV2Payload | None = None
    error: ErrorBody | None = None
