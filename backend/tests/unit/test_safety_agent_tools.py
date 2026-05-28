"""build_safety_tools 工具行为测试。

覆盖：
- submit_safety_report：合法 JSON → 写入 sink；JSON 解析失败 → is_error；
  schema 校验失败 → is_error + 第一条错误清晰
- sink 累加：连续 submit 都会追加（agent 一般只取最新 / 报错复跑）

`load_scenario_skill` 已下线（12 个场景全部 inline 进 system prompt），相关测试
亦同步移除。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.safety_agent.loader import SkillLoader
from app.safety_agent.tools import build_safety_tools, build_scene_detection_tool
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


def test_build_safety_tools_only_returns_submit(tools_and_sink) -> None:
    """回归保护：当前只返回 submit_safety_report 一个工具。load_scenario_skill 已下线。"""
    by_name, _ = tools_and_sink
    assert set(by_name.keys()) == {"submit_safety_report"}


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


# ============== v4 两阶段：submit_scene_detection 工具 ==============


@pytest.fixture
def detection_tool_and_sink(loader: SkillLoader):
    sink: list[list[str]] = []
    tools = build_scene_detection_tool(loader, sink)
    return tools[0], sink


async def test_scene_detection_valid_ids_persisted(detection_tool_and_sink) -> None:
    """合法 ID 列表 → sink 追加，返回 is_error 不出现。"""
    tool, sink = detection_tool_and_sink
    result = await tool.handler({"scenes": ["S03", "S05"]})
    assert "is_error" not in result
    assert sink == [["S03", "S05"]]


async def test_scene_detection_filters_unknown_ids(detection_tool_and_sink) -> None:
    """混合合法 + 未知 ID → 过滤掉未知的，sink 只存合法的，返回 ok 不是 is_error。"""
    tool, sink = detection_tool_and_sink
    result = await tool.handler({"scenes": ["S03", "S99", "S05", "ZZZ"]})
    assert "is_error" not in result
    assert sink == [["S03", "S05"]]
    # 提示文本里要告诉模型哪些被忽略了
    assert "S99" in result["content"][0]["text"] or "ZZZ" in result["content"][0]["text"]


async def test_scene_detection_all_unknown_returns_error(detection_tool_and_sink) -> None:
    """全部 ID 都非法 → is_error，sink 不变。"""
    tool, sink = detection_tool_and_sink
    result = await tool.handler({"scenes": ["S99", "ZZZ"]})
    assert result.get("is_error") is True
    assert sink == []


async def test_scene_detection_wrong_type_returns_error(detection_tool_and_sink) -> None:
    """scenes 不是字符串列表 → is_error。"""
    tool, sink = detection_tool_and_sink
    result = await tool.handler({"scenes": "S03"})  # 字符串而非列表
    assert result.get("is_error") is True
    assert sink == []


async def test_scene_detection_mixed_type_returns_error(detection_tool_and_sink) -> None:
    """列表里混了非字符串 → is_error。"""
    tool, sink = detection_tool_and_sink
    result = await tool.handler({"scenes": ["S03", 5]})
    assert result.get("is_error") is True
    assert sink == []


async def test_scene_detection_metric_accepted(detection_tool_and_sink, caplog) -> None:
    tool, _ = detection_tool_and_sink
    with caplog.at_level("INFO", logger="app.safety_agent.tools"):
        await tool.handler({"scenes": ["S03"]})
    metrics = [
        r for r in caplog.records
        if getattr(r, "metric", "") == "v2.tool.scene_detection.accepted"
    ]
    assert metrics, "成功 detection 应埋 v2.tool.scene_detection.accepted"
    assert metrics[0].scenes == ["S03"]


async def test_scene_detection_metric_partial_unknown(detection_tool_and_sink, caplog) -> None:
    tool, _ = detection_tool_and_sink
    with caplog.at_level("INFO", logger="app.safety_agent.tools"):
        await tool.handler({"scenes": ["S03", "S99"]})
    metrics = [
        r for r in caplog.records
        if getattr(r, "metric", "") == "v2.tool.scene_detection.partial_unknown"
    ]
    assert metrics, "部分未知 ID 应埋 partial_unknown"
    assert metrics[0].ignored == ["S99"]


async def test_scene_detection_metric_all_unknown(detection_tool_and_sink, caplog) -> None:
    tool, _ = detection_tool_and_sink
    with caplog.at_level("WARNING", logger="app.safety_agent.tools"):
        await tool.handler({"scenes": ["S99", "ZZZ"]})
    metrics = [
        r for r in caplog.records
        if getattr(r, "metric", "") == "v2.tool.scene_detection.all_unknown"
    ]
    assert metrics, "全 unknown 应埋 all_unknown"


# ---------- loader subset 行为 ----------


def test_loader_get_scenarios_inline_subset(loader: SkillLoader) -> None:
    """get_scenarios_inline(ids) 只包含指定子集；不在列表里的不应出现 L2 内容。"""
    only_s03 = loader.get_scenarios_inline(scenario_ids=["S03"])
    assert "S03" in only_s03
    # S03 的 L2 至少包含"脚手架"这种主题词
    assert "脚手架" in only_s03
    # 其他场景不应被 inline
    # 用 S08 起重机械 / S07 施工用电的标题
    all_inline = loader.get_scenarios_inline()
    assert len(only_s03) < len(all_inline) / 3, "单场景子集应远小于全 inline"


def test_loader_get_scenarios_inline_none_equals_all(loader: SkillLoader) -> None:
    """get_scenarios_inline(None) ≡ get_all_scenarios_inline()（向后兼容）。"""
    assert loader.get_scenarios_inline(None) == loader.get_all_scenarios_inline()


def test_loader_get_scenarios_inline_unknown_ids_ignored(loader: SkillLoader) -> None:
    """未知 ID 静默忽略，不报错。"""
    only_unknown = loader.get_scenarios_inline(scenario_ids=["S99", "ZZZ"])
    assert only_unknown == ""  # 没匹配上任何场景
    mixed = loader.get_scenarios_inline(scenario_ids=["S03", "S99"])
    assert "S03" in mixed
