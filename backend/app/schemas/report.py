"""Report payload Pydantic models.

对齐 docs/specs/report-schema.md。任何字段变更必须同 PR 改 spec 文档。
"""

from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["high", "medium", "low"]
CategoryCode = Literal["H1", "H2", "H3", "H4", "H5", "H6", "H7", "H8", "H9", "H10"]


class Hazard(BaseModel):
    category_code: CategoryCode
    category_name: str
    description: str = Field(max_length=100)
    severity: Severity
    regulation: str = ""
    suggestion: str = Field(max_length=100)
    # 重大事故隐患（建质规〔2024〕5号）；命中即上报义务，前端红标区分。
    # 默认值保证向后兼容：旧 LLM 响应未带这两个字段时仍可解析。
    is_major: bool = False
    major_basis: str = ""


class ModelMeta(BaseModel):
    provider: Literal["claude_cli", "doubao", "fake"]
    model: str
    latency_ms: int = Field(ge=0)


class ReportPayload(BaseModel):
    inspection_id: str
    created_at: str
    plain_warning: str = Field(max_length=30)
    summary: str = Field(max_length=100)
    overall_severity: Severity
    hazards: list[Hazard]
    model_meta: ModelMeta
