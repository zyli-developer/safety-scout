"""parse_report 4 级容错策略。"""

from pathlib import Path

import pytest

from app.errors import LLMParseError
from app.llm.parser import parse_report

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "malformed"

MINIMAL_VALID_JSON = """
{
  "inspection_id": "550e8400-e29b-41d4-a716-446655440000",
  "created_at": "2026-05-18T00:00:00Z",
  "plain_warning": "测试",
  "summary": "现场无明显隐患。",
  "overall_severity": "low",
  "hazards": [],
  "model_meta": {"provider": "claude_cli", "model": "x", "latency_ms": 100}
}
"""


async def test_L1_pure_json():
    """L1：纯 JSON 字符串直接 json.loads 通过。"""
    payload = await parse_report(MINIMAL_VALID_JSON)
    assert payload.overall_severity == "low"


async def test_L2_json_wrapped_in_markdown():
    """L2：JSON 被 ```json fence 包裹 + 前后有文字，regex 抽出来。"""
    raw = FIXTURES.joinpath("wrapped_in_markdown.txt").read_text(encoding="utf-8")
    payload = await parse_report(raw)
    assert payload.plain_warning == "测试"


async def test_L2_markdown_wrapped_with_nested_hazard_objects():
    """L2 关键回归：markdown 包裹 + hazards 数组里有多个 {...} 子对象。

    case_002 实测暴露的 bug：旧 parser 非贪心优先，finditer 优先返回了
    hazards[0] 这个 dict（它本身也是合法 JSON），把不完整 hazard 当报告
    抛给 Pydantic 校验。修复：候选 dict 必须能通过 ReportPayload 校验
    才算命中；贪心整体抓优先。
    """
    raw = '''```json
{
  "inspection_id": "550e8400-e29b-41d4-a716-446655440000",
  "created_at": "2026-05-19T00:00:00Z",
  "plain_warning": "嵌套测试",
  "summary": "包含嵌套对象的报告。",
  "overall_severity": "high",
  "hazards": [
    {"category_code": "H1", "category_name": "高处坠落",
     "description": "x", "severity": "high",
     "regulation": "", "suggestion": "y"},
    {"category_code": "H2", "category_name": "物体打击",
     "description": "z", "severity": "medium",
     "regulation": "", "suggestion": "w"}
  ],
  "model_meta": {"provider": "claude_cli", "model": "x", "latency_ms": 100}
}
```
'''
    payload = await parse_report(raw)
    assert payload.plain_warning == "嵌套测试"
    assert len(payload.hazards) == 2
    assert payload.hazards[0].category_code == "H1"
    assert payload.hazards[1].category_code == "H2"


async def test_L3_reprompt_recovers():
    """L3：第一次响应是垃圾、reprompt 后返回合法 JSON。"""
    call_count = {"n": 0}

    async def fake_reprompt(original: str) -> str:
        call_count["n"] += 1
        assert "你上一次的输出不是合法的 JSON 对象" in original
        assert raw in original  # 确保 reprompt template 把原响应嵌进去了
        return MINIMAL_VALID_JSON

    raw = "I cannot analyze this image."
    payload = await parse_report(raw, reprompt=fake_reprompt)
    assert payload.overall_severity == "low"
    assert call_count["n"] == 1


async def test_L4_raise_after_reprompt_also_fails():
    """L4：reprompt 后还是垃圾，抛 LLMParseError。"""

    async def fake_reprompt(original: str) -> str:
        return "still cannot parse"

    raw = FIXTURES.joinpath("garbage_no_json.txt").read_text(encoding="utf-8")
    with pytest.raises(LLMParseError):
        await parse_report(raw, reprompt=fake_reprompt)


async def test_L4_no_reprompt_provided_and_invalid():
    """无 reprompt 注入时，L1/L2 都不过直接抛 LLMParseError。"""
    raw = "totally invalid"
    with pytest.raises(LLMParseError):
        await parse_report(raw, reprompt=None)


async def test_is_major_round_trip_when_present():
    """重大事故隐患（建质规〔2024〕5号）：响应带 is_major + major_basis 时正常通过。"""
    raw = """
    {
      "inspection_id": "550e8400-e29b-41d4-a716-446655440000",
      "created_at": "2026-05-25T00:00:00Z",
      "plain_warning": "临边没护栏，要坠人",
      "summary": "现场存在 1 项重大隐患。",
      "overall_severity": "high",
      "hazards": [
        {
          "category_code": "H1",
          "category_name": "高处坠落",
          "description": "二层楼板临边无防护",
          "severity": "high",
          "regulation": "《建筑施工高处作业安全技术规范》JGJ 80-2016 第 4.2.1 条",
          "suggestion": "24 小时内补 1.2m 防护栏",
          "is_major": true,
          "major_basis": "《房屋市政工程生产安全重大事故隐患判定标准（2024版）》建质规〔2024〕5号 第十一条 高处作业 — 临边、洞口防护缺失"
        }
      ],
      "model_meta": {"provider": "claude_cli", "model": "x", "latency_ms": 100}
    }
    """
    payload = await parse_report(raw)
    assert payload.hazards[0].is_major is True
    assert "建质规〔2024〕5号" in payload.hazards[0].major_basis


async def test_is_major_defaults_to_false_when_absent():
    """旧响应（无 is_major/major_basis 字段）必须仍可解析；默认 False/空字符串。"""
    # MINIMAL_VALID_JSON 本身就不含这两个字段，但 hazards 为空，覆盖不全；
    # 这里造一条 hazard 但显式不带 is_major，确认 Pydantic 走默认值。
    raw = """
    {
      "inspection_id": "550e8400-e29b-41d4-a716-446655440000",
      "created_at": "2026-05-25T00:00:00Z",
      "plain_warning": "测试",
      "summary": "x",
      "overall_severity": "low",
      "hazards": [
        {
          "category_code": "H10",
          "category_name": "其他",
          "description": "x",
          "severity": "low",
          "regulation": "",
          "suggestion": "x"
        }
      ],
      "model_meta": {"provider": "claude_cli", "model": "x", "latency_ms": 100}
    }
    """
    payload = await parse_report(raw)
    assert payload.hazards[0].is_major is False
    assert payload.hazards[0].major_basis == ""


async def test_pydantic_validation_failure_also_raises():
    """JSON 解析通过但 Pydantic 校验失败（如 category_code=H99），抛 LLMParseError。"""
    bad = """
    {
      "inspection_id": "550e8400-e29b-41d4-a716-446655440000",
      "created_at": "2026-05-18T00:00:00Z",
      "plain_warning": "测试",
      "summary": "x",
      "overall_severity": "high",
      "hazards": [
        {
          "category_code": "H99",
          "category_name": "x",
          "description": "x",
          "severity": "high",
          "regulation": "",
          "suggestion": "x"
        }
      ],
      "model_meta": {"provider": "claude_cli", "model": "x", "latency_ms": 100}
    }
    """
    with pytest.raises(LLMParseError):
        await parse_report(bad)
