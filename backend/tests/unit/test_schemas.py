"""ReportPayload Pydantic 模型对齐 docs/specs/report-schema.md。"""

import json
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.report import Hazard, ModelMeta, ReportPayload


def test_minimal_valid_report():
    payload = ReportPayload(
        inspection_id="550e8400-e29b-41d4-a716-446655440000",
        created_at="2026-05-18T08:23:11Z",
        plain_warning="工人未戴安全帽，立刻撤离",
        summary="现场存在 1 项高风险隐患。",
        overall_severity="high",
        hazards=[
            Hazard(
                category_code="H9",
                category_name="个人防护缺失",
                description="2 名工人未佩戴安全帽",
                severity="high",
                regulation="",
                suggestion="立即责令补齐安全帽",
            )
        ],
        model_meta=ModelMeta(provider="doubao", model="doubao-vision-1.5-pro", latency_ms=12345),
    )
    assert payload.overall_severity == "high"
    assert payload.hazards[0].category_code == "H9"


def test_severity_enum_rejects_invalid():
    with pytest.raises(ValidationError):
        Hazard(
            category_code="H1", category_name="高处坠落",
            description="x", severity="critical",  # 非法
            regulation="", suggestion="x",
        )


def test_category_code_must_be_h1_to_h10():
    with pytest.raises(ValidationError):
        Hazard(
            category_code="H11",  # 非法
            category_name="x",
            description="x", severity="high",
            regulation="", suggestion="x",
        )


def test_regulation_can_be_empty_string():
    h = Hazard(
        category_code="H10", category_name="文明施工",
        description="x", severity="low",
        regulation="",  # 允许空
        suggestion="x",
    )
    assert h.regulation == ""


def test_empty_hazards_list_allowed():
    p = ReportPayload(
        inspection_id="550e8400-e29b-41d4-a716-446655440000",
        created_at="2026-05-18T00:00:00Z",
        plain_warning="未识别到隐患",
        summary="现场未识别到明显隐患。",
        overall_severity="low",
        hazards=[],
        model_meta=ModelMeta(provider="doubao", model="x", latency_ms=100),
    )
    assert p.hazards == []


SPEC_PATH = Path(__file__).resolve().parents[3] / "docs" / "specs" / "report-schema.md"


def _extract_first_json_block(md: str) -> dict:
    """从 markdown 中抽第一个 ```json 代码块并解析。"""
    m = re.search(r"```json\s*\n(.*?)\n```", md, re.DOTALL)
    if not m:
        raise AssertionError("report-schema.md 中找不到 ```json 代码块")
    return json.loads(m.group(1))


def test_spec_example_validates_against_pydantic():
    """报告 schema spec 里的示例 JSON 必须通过 Pydantic 校验。

    spec 改了但 Pydantic 没跟，这个测试会挂。
    """
    spec_md = SPEC_PATH.read_text(encoding="utf-8")
    example = _extract_first_json_block(spec_md)
    ReportPayload(**example)  # 不抛 = 通过
