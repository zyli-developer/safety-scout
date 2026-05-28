"""v2 报告 schema —— 对齐 safety_skills/_shared/output_schema.md。

与 v1 ReportPayload 的差异（不做向后兼容，dev 阶段）：
- 字段更细：split 出 report_meta / findings / no_findings / uncertain / summary
- severity 改用中文档位（重大 / 较大 / 一般 / 低）—— 与规范文档措辞一致
- 新增 check_id（清单条目编号）、location（图片相对位置）、confidence（模型把握度）
- no_findings：证明检查过哪些项（防止"漏检装作不存在"）
- uncertain：模型无法判断的项（避免幻觉）

`ReportV2Payload.model_validate(...)` 是 v2 路径的唯一信任边界 —— Agent 输出的
JSON 必须能在这里通过，否则 submit_safety_report tool 返 is_error 让 Agent 重试。
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["重大", "较大", "一般", "低"]
Confidence = Literal["高", "中", "低"]
FindingStatus = Literal["存在隐患", "不存在", "无法判断"]


class ReportMeta(BaseModel):
    """report_meta 段 —— 整图概述 + 命中场景。"""

    model_config = ConfigDict(extra="forbid")

    image_summary: str = Field(min_length=1, description="对图片整体场景的一句话描述")
    scene_detected: list[str] = Field(
        default_factory=list,
        description="命中的场景 ID 列表，如 ['S03', 'S05']",
    )
    analysis_confidence: Confidence
    overall_risk_level: Severity


class Finding(BaseModel):
    """单条隐患 —— 必须有 check_id + severity（plan §2.1 强约束）。"""

    model_config = ConfigDict(extra="forbid")

    check_id: str = Field(min_length=1, description="L1/L2 清单条目编号，如 B01 或 S03-A01")
    category: str = Field(min_length=1, description="风险类别，如 高坠风险 / 触电")
    status: FindingStatus = "存在隐患"
    title: str = Field(min_length=1)
    location: str = Field(min_length=1, description="图片相对位置，便于人工复核")
    description: str = Field(min_length=1)
    severity: Severity
    regulation: str = Field(default="", description="引用的规范条款编号")
    action: str = Field(min_length=1, description="给安全员的整改建议，动作可执行")
    confidence: Confidence
    # 重大事故隐患（建质规〔2024〕5号）—— 模型自行判定，不允许仅凭 severity=重大 等价代换。
    # 默认 false / 空串：前端 adapter 直接 pass-through，不再合成假依据。
    is_major: bool = Field(
        default=False,
        description="是否命中《房屋市政工程生产安全重大事故隐患判定标准（2024版）》",
    )
    major_basis: str = Field(
        default="",
        description="is_major=true 时引用的判定标准条款；不确信留空",
    )


class NoFinding(BaseModel):
    """已核查但未发现隐患的项 —— 证明检查过。"""

    model_config = ConfigDict(extra="forbid")

    check_id: str = Field(min_length=1)
    note: str = Field(min_length=1)


class Uncertain(BaseModel):
    """无法判断的项 —— 避免幻觉，明确给出后续核查建议。"""

    model_config = ConfigDict(extra="forbid")

    check_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    suggested_action: str = Field(min_length=1)


class ReportSummary(BaseModel):
    """summary 段 —— 计数 + 关键建议。"""

    model_config = ConfigDict(extra="forbid")

    total_checks: int = Field(ge=0)
    findings_count: int = Field(ge=0)
    fatal_count: int = Field(ge=0)
    major_count: int = Field(ge=0)
    minor_count: int = Field(ge=0)
    no_issue_count: int = Field(ge=0)
    uncertain_count: int = Field(ge=0)
    key_recommendations: list[str] = Field(default_factory=list)


class ReportV2Payload(BaseModel):
    """v2 报告完整体 —— 与 output_schema.md 一一对应。

    历史：曾给 `no_findings`/`uncertain` 加 `max_length=5/3` 硬约束（structured
    output 模式下 CLI 会把它编进 json_schema 强制模型按上限生成）。但生产实测
    Sonnet 4.6 满足不了这个硬约束 —— 模型反复生成 N+1 条触发 CLI retry，5 次
    后放弃，整次请求超时（实测一张图 365s 超 360s timeout）。已撤销。

    现状：体量约束仅放在 prompt（"最多 5/3 条"是 soft 建议），由模型自行遵守。
    实测 Sonnet 通常会遵守 80%+，少数超 1-2 条可接受；比硬约束触发 retry 死循环
    可靠得多。findings 不设任何上限。
    """

    model_config = ConfigDict(extra="forbid")

    report_meta: ReportMeta
    findings: list[Finding] = Field(default_factory=list)
    no_findings: list[NoFinding] = Field(default_factory=list)
    uncertain: list[Uncertain] = Field(default_factory=list)
    summary: ReportSummary
