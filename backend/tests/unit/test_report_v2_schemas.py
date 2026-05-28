"""ReportV2Payload 校验测试 —— output_schema.md 的合同体现。

关键 case：
- 文档示例 JSON（happy path）能解析
- 必填字段缺失 → ValidationError
- severity / status / confidence 枚举值不在白名单 → ValidationError
- 计数字段为负 → ValidationError
- 额外字段（extra='forbid'） → ValidationError
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.report_v2 import ReportV2Payload

DOC_EXAMPLE = {
    "report_meta": {
        "image_summary": "在建主体结构外侧，落地式脚手架，工人正在绑扎钢筋",
        "scene_detected": ["S03", "S05", "S07"],
        "analysis_confidence": "高",
        "overall_risk_level": "重大",
    },
    "findings": [
        {
            "check_id": "B01",
            "category": "高坠风险",
            "status": "存在隐患",
            "title": "三层临边未设置防护栏杆",
            "location": "图片中部，三层楼板边缘",
            "description": "三层楼板东侧边缘（落差约 6m）未见任何防护栏杆",
            "severity": "重大",
            "regulation": "JGJ80-2016 第 4.1.1 条",
            "action": "立即停工，搭设标准防护栏杆",
            "confidence": "高",
        }
    ],
    "no_findings": [{"check_id": "A01", "note": "图中可见 4 名工人均佩戴黄色安全帽"}],
    "uncertain": [
        {
            "check_id": "S03-A03",
            "reason": "立杆垂直度需要现场测量",
            "suggested_action": "建议现场用线锤复测",
        }
    ],
    "summary": {
        "total_checks": 95,
        "findings_count": 5,
        "fatal_count": 2,
        "major_count": 1,
        "minor_count": 2,
        "no_issue_count": 78,
        "uncertain_count": 12,
        "key_recommendations": ["立即停工整改 2 项重大隐患"],
    },
}


def test_doc_example_parses() -> None:
    report = ReportV2Payload.model_validate(DOC_EXAMPLE)
    assert report.report_meta.image_summary.startswith("在建主体")
    assert report.findings[0].severity == "重大"
    assert report.summary.fatal_count == 2


def test_missing_top_level_field_rejected() -> None:
    bad = dict(DOC_EXAMPLE)
    del bad["summary"]
    with pytest.raises(ValidationError) as exc:
        ReportV2Payload.model_validate(bad)
    assert any(e["loc"] == ("summary",) for e in exc.value.errors())


def test_invalid_severity_rejected() -> None:
    bad = {**DOC_EXAMPLE, "findings": [{**DOC_EXAMPLE["findings"][0], "severity": "high"}]}
    with pytest.raises(ValidationError):
        ReportV2Payload.model_validate(bad)


def test_invalid_confidence_rejected() -> None:
    bad = {
        **DOC_EXAMPLE,
        "report_meta": {**DOC_EXAMPLE["report_meta"], "analysis_confidence": "very high"},
    }
    with pytest.raises(ValidationError):
        ReportV2Payload.model_validate(bad)


def test_invalid_status_rejected() -> None:
    bad = {**DOC_EXAMPLE, "findings": [{**DOC_EXAMPLE["findings"][0], "status": "确认"}]}
    with pytest.raises(ValidationError):
        ReportV2Payload.model_validate(bad)


def test_negative_count_rejected() -> None:
    bad = {**DOC_EXAMPLE, "summary": {**DOC_EXAMPLE["summary"], "fatal_count": -1}}
    with pytest.raises(ValidationError):
        ReportV2Payload.model_validate(bad)


def test_extra_field_rejected() -> None:
    bad = {**DOC_EXAMPLE, "unexpected_field": "x"}
    with pytest.raises(ValidationError):
        ReportV2Payload.model_validate(bad)


def test_findings_empty_list_allowed() -> None:
    """无隐患的图也应通过 —— findings 默认空列表。"""
    good = {**DOC_EXAMPLE, "findings": []}
    report = ReportV2Payload.model_validate(good)
    assert report.findings == []


def test_no_findings_no_schema_cap() -> None:
    """回归保护：no_findings 不应有 schema max_length —— Sonnet 4.6 满足不了，会
    触发 CLI 的 structured-output retry 死循环（实测 5 次 retry 571s 后放弃，
    总耗时超 360s timeout，整次请求挂掉）。体量约束只走 prompt soft 提示。

    曾经版本：no_findings max_length=5 → 生产挂；现已撤销。
    """
    many = [{"check_id": f"X{i:02d}", "note": "已检查"} for i in range(30)]
    good = {**DOC_EXAMPLE, "no_findings": many}
    report = ReportV2Payload.model_validate(good)
    assert len(report.no_findings) == 30


def test_uncertain_no_schema_cap() -> None:
    """同 no_findings：uncertain 不应有 schema max_length。"""
    many = [
        {"check_id": f"U{i:02d}", "reason": "不确定", "suggested_action": "复核"}
        for i in range(30)
    ]
    good = {**DOC_EXAMPLE, "uncertain": many}
    report = ReportV2Payload.model_validate(good)
    assert len(report.uncertain) == 30


def test_findings_no_schema_cap() -> None:
    """findings 不能设上限 —— 真隐患不能丢；超过 10 条也必须通过。"""
    many_findings = [
        {**DOC_EXAMPLE["findings"][0], "check_id": f"F{i:02d}"} for i in range(12)
    ]
    good = {**DOC_EXAMPLE, "findings": many_findings}
    report = ReportV2Payload.model_validate(good)
    assert len(report.findings) == 12


def test_finding_check_id_required() -> None:
    bad = {
        **DOC_EXAMPLE,
        "findings": [{k: v for k, v in DOC_EXAMPLE["findings"][0].items() if k != "check_id"}],
    }
    with pytest.raises(ValidationError) as exc:
        ReportV2Payload.model_validate(bad)
    locs = {e["loc"] for e in exc.value.errors()}
    assert any("check_id" in str(loc) for loc in locs)


def test_is_major_defaults_false_and_basis_empty() -> None:
    """旧响应不带 is_major / major_basis 时仍可解析 —— 模型保守留空。"""
    report = ReportV2Payload.model_validate(DOC_EXAMPLE)
    assert report.findings[0].is_major is False
    assert report.findings[0].major_basis == ""


def test_is_major_with_basis_passes_through() -> None:
    """模型主动填 is_major + major_basis 时，schema 原样保留 —— adapter 才拿得到真值。"""
    good = {
        **DOC_EXAMPLE,
        "findings": [
            {
                **DOC_EXAMPLE["findings"][0],
                "is_major": True,
                "major_basis": (
                    "《房屋市政工程生产安全重大事故隐患判定标准（2024版）》"
                    "建质规〔2024〕5号 第 6 条 高处作业 — 临边高度 ≥2m 无防护栏"
                ),
            }
        ],
    }
    report = ReportV2Payload.model_validate(good)
    assert report.findings[0].is_major is True
    assert "建质规〔2024〕5号" in report.findings[0].major_basis
