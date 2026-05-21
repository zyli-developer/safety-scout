"""build_safety_tools 工具行为测试。

覆盖：
- load_scenario_skill：合法 ID → 返回 markdown；非法 ID → is_error + 可用列表
- submit_safety_report：合法 JSON → 写入 sink；JSON 解析失败 → is_error；
  schema 校验失败 → is_error + 第一条错误清晰
- sink 累加：连续 submit 都会追加（agent 一般只取最新 / 报错复跑）
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.safety_agent.loader import SkillLoader
from app.safety_agent.tools import build_safety_tools
from app.schemas.report_v2 import ReportV2Payload

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILLS_ROOT = REPO_ROOT / "safety_skills"

VALID_REPORT = {
    "report_meta": {
        "image_summary": "工地脚手架作业面",
        "scene_detected": ["S03"],
        "analysis_confidence": "高",
        "overall_risk_level": "较大",
    },
    "findings": [
        {
            "check_id": "B01",
            "category": "高坠",
            "status": "存在隐患",
            "title": "临边无栏杆",
            "location": "图片中部",
            "description": "三层楼板东侧未见栏杆",
            "severity": "重大",
            "regulation": "JGJ80-2016 4.1.1",
            "action": "搭设标准防护栏杆",
            "confidence": "高",
        }
    ],
    "no_findings": [],
    "uncertain": [],
    "summary": {
        "total_checks": 35,
        "findings_count": 1,
        "fatal_count": 1,
        "major_count": 0,
        "minor_count": 0,
        "no_issue_count": 30,
        "uncertain_count": 4,
        "key_recommendations": ["立即停工整改"],
    },
}


@pytest.fixture
def loader() -> SkillLoader:
    if not SKILLS_ROOT.is_dir():
        pytest.skip(f"safety_skills 未部署到 {SKILLS_ROOT}")
    return SkillLoader(SKILLS_ROOT)


@pytest.fixture
def tools_and_sink(loader: SkillLoader):
    sink: list[ReportV2Payload] = []
    tools = build_safety_tools(loader, sink)
    by_name = {t.name: t for t in tools}
    return by_name, sink


async def test_load_scenario_known(tools_and_sink) -> None:
    by_name, _ = tools_and_sink
    result = await by_name["load_scenario_skill"].handler({"scenario_id": "S03"})
    assert "is_error" not in result
    text = result["content"][0]["text"]
    assert "S03" in text
    assert "脚手架" in text


async def test_load_scenario_unknown(tools_and_sink) -> None:
    by_name, _ = tools_and_sink
    result = await by_name["load_scenario_skill"].handler({"scenario_id": "S99"})
    assert result.get("is_error") is True
    text = result["content"][0]["text"]
    assert "S99" in text
    assert "S03" in text  # 可用列表至少包含 S03


async def test_load_scenario_empty_id(tools_and_sink) -> None:
    by_name, _ = tools_and_sink
    result = await by_name["load_scenario_skill"].handler({"scenario_id": ""})
    assert result.get("is_error") is True


async def test_submit_valid_report_writes_sink(tools_and_sink) -> None:
    by_name, sink = tools_and_sink
    result = await by_name["submit_safety_report"].handler(
        {"report_json": json.dumps(VALID_REPORT, ensure_ascii=False)}
    )
    assert "is_error" not in result
    assert len(sink) == 1
    assert sink[0].findings[0].check_id == "B01"


async def test_submit_invalid_json_returns_error(tools_and_sink) -> None:
    by_name, sink = tools_and_sink
    result = await by_name["submit_safety_report"].handler(
        {"report_json": "{this is: not json"}
    )
    assert result.get("is_error") is True
    assert "JSON 解析失败" in result["content"][0]["text"]
    assert sink == []


async def test_submit_invalid_schema_returns_error(tools_and_sink) -> None:
    by_name, sink = tools_and_sink
    bad = {**VALID_REPORT}
    bad["findings"] = [{**VALID_REPORT["findings"][0], "severity": "high"}]  # 不在枚举
    result = await by_name["submit_safety_report"].handler(
        {"report_json": json.dumps(bad, ensure_ascii=False)}
    )
    assert result.get("is_error") is True
    assert "schema 校验失败" in result["content"][0]["text"]
    assert sink == []


async def test_submit_empty_string_returns_error(tools_and_sink) -> None:
    by_name, _ = tools_and_sink
    result = await by_name["submit_safety_report"].handler({"report_json": ""})
    assert result.get("is_error") is True


async def test_two_valid_submits_both_appended(tools_and_sink) -> None:
    """sink 累加：Agent 偶尔会重提交，宿主取 sink[-1]。"""
    by_name, sink = tools_and_sink
    raw = json.dumps(VALID_REPORT, ensure_ascii=False)
    await by_name["submit_safety_report"].handler({"report_json": raw})
    await by_name["submit_safety_report"].handler({"report_json": raw})
    assert len(sink) == 2


# ---------- plan §3.3 日志埋点：metric 标签覆盖 ----------


async def test_metric_log_on_load_hit(tools_and_sink, caplog) -> None:
    by_name, _ = tools_and_sink
    with caplog.at_level("INFO", logger="app.safety_agent.tools"):
        await by_name["load_scenario_skill"].handler({"scenario_id": "S03"})
    metrics = [r for r in caplog.records if getattr(r, "metric", "") == "v2.tool.load_scenario.hit"]
    assert metrics, "load hit 应埋 v2.tool.load_scenario.hit"
    assert metrics[0].scenario_id == "S03"


async def test_metric_log_on_load_unknown(tools_and_sink, caplog) -> None:
    by_name, _ = tools_and_sink
    with caplog.at_level("WARNING", logger="app.safety_agent.tools"):
        await by_name["load_scenario_skill"].handler({"scenario_id": "S99"})
    metrics = [
        r for r in caplog.records if getattr(r, "metric", "") == "v2.tool.load_scenario.unknown_id"
    ]
    assert metrics, "unknown_id 应埋 v2.tool.load_scenario.unknown_id"
    assert metrics[0].scenario_id == "S99"


async def test_metric_log_on_submit_accepted(tools_and_sink, caplog) -> None:
    by_name, _ = tools_and_sink
    with caplog.at_level("INFO", logger="app.safety_agent.tools"):
        await by_name["submit_safety_report"].handler(
            {"report_json": json.dumps(VALID_REPORT, ensure_ascii=False)}
        )
    metrics = [r for r in caplog.records if getattr(r, "metric", "") == "v2.tool.submit.accepted"]
    assert metrics, "submit 成功应埋 v2.tool.submit.accepted"
    rec = metrics[0]
    assert rec.findings_count == 1
    assert rec.severity_distribution == {"重大": 1, "较大": 0, "一般": 0, "低": 0}
    assert rec.scene_detected == ["S03"]


async def test_metric_log_on_submit_json_error(tools_and_sink, caplog) -> None:
    by_name, _ = tools_and_sink
    with caplog.at_level("WARNING", logger="app.safety_agent.tools"):
        await by_name["submit_safety_report"].handler({"report_json": "{not json"})
    metrics = [r for r in caplog.records if getattr(r, "metric", "") == "v2.tool.submit.json_error"]
    assert metrics, "JSON 错误应埋 v2.tool.submit.json_error"


async def test_metric_log_on_submit_schema_error(tools_and_sink, caplog) -> None:
    by_name, _ = tools_and_sink
    bad = {**VALID_REPORT, "findings": [{**VALID_REPORT["findings"][0], "severity": "high"}]}
    with caplog.at_level("WARNING", logger="app.safety_agent.tools"):
        await by_name["submit_safety_report"].handler(
            {"report_json": json.dumps(bad, ensure_ascii=False)}
        )
    metrics = [
        r for r in caplog.records if getattr(r, "metric", "") == "v2.tool.submit.schema_error"
    ]
    assert metrics, "schema 错误应埋 v2.tool.submit.schema_error"
    assert metrics[0].first_loc.startswith("findings.0.severity")
