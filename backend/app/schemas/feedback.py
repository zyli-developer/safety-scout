"""Badcase 反馈 schema —— POST /api/v2/inspections/{id}/feedback。

设计动机（plan §5.3 + docs/specs/v2-rollout.md §二）：
- 模型识别能力提升靠"反馈 → 调 Skill markdown"闭环
- 反馈表独立于 inspections 表，避免反馈写入污染主流程
- kind 三档对齐前端可枚举的按钮：误报 / 漏报 / 整改建议不可执行

约束：
- kind="false_positive"（误报）：必须有 check_id —— 误报必然针对某条 finding
- kind="bad_action"（建议不可执行）：必须有 check_id —— 不可执行必然针对某条 finding
- kind="missed"（漏报）：check_id 可空 —— 漏报本质就是 "你没识别到 X"
- description 必填且 ≤ 500 字 —— 写人话上下文，便于安全工程师反查
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

FeedbackKind = Literal["false_positive", "missed", "bad_action"]


class FeedbackCreate(BaseModel):
    """POST body —— 前端发起反馈时填的内容。"""

    kind: FeedbackKind
    check_id: str | None = Field(
        default=None,
        max_length=32,
        description="L1/L2 清单条目编号，false_positive/bad_action 时必填；missed 时可空",
    )
    description: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def _require_check_id_for_targeted_kinds(self) -> FeedbackCreate:
        if self.kind in ("false_positive", "bad_action") and not self.check_id:
            raise ValueError(
                f"kind={self.kind} 必须带 check_id（指向被反馈的 finding）"
            )
        return self


class FeedbackCreateResponse(BaseModel):
    """POST 201 响应 —— 给前端确认反馈已落地。"""

    feedback_id: str
    inspection_id: str
    created_at: str
