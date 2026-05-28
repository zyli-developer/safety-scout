"""analyze_image orchestration 测试 —— 不打 Claude，靠 monkeypatch 模拟 SDK。

策略：
- monkeypatch `app.safety_agent.agent.build_safety_tools` 同时捕获 sink + tools
  （这样在 fake_query 里能拿到 submit 工具来注入报告 / 不注入报告）
- monkeypatch `app.safety_agent.agent.query` 为 async generator，yield ResultMessage
- 覆盖：happy / 未 submit / SDK 异常 / 超时
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from app.config import Settings
from app.errors import LLMCallError, LLMTimeoutError
from app.safety_agent import agent as agent_mod
from app.safety_agent.loader import SkillLoader
from app.safety_agent.tools import build_safety_tools as _real_build_safety_tools

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILLS_ROOT = REPO_ROOT / "safety_skills"

VALID_REPORT = {
    "report_meta": {
        "image_summary": "脚手架作业面",
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
            "regulation": "JGJ80-2016",
            "action": "立即停工搭设栏杆",
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
        "key_recommendations": ["立即停工"],
    },
}


def _make_result_message(
    input_tokens: int = 1000,
    output_tokens: int = 200,
    cache_read_input_tokens: int = 0,
    cache_creation_input_tokens: int = 0,
):
    """构造一个最小可用的 ResultMessage（字段跟 SDK 0.2.83 对齐）。"""
    from claude_agent_sdk import ResultMessage

    return ResultMessage(
        subtype="result",
        duration_ms=2500,
        duration_api_ms=2000,
        is_error=False,
        num_turns=3,
        session_id="test-session",
        total_cost_usd=0.012,
        usage={
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_read_input_tokens": cache_read_input_tokens,
            "cache_creation_input_tokens": cache_creation_input_tokens,
        },
    )


@pytest.fixture
def skill_loader() -> SkillLoader:
    if not SKILLS_ROOT.is_dir():
        pytest.skip(f"safety_skills 未部署到 {SKILLS_ROOT}")
    return SkillLoader(SKILLS_ROOT)


@pytest.fixture
def settings() -> Settings:
    # 默认 90s 太长；测里都用 5s
    return Settings(agent_timeout_seconds=5, safety_skills_root=SKILLS_ROOT)


@pytest.fixture
def spy_build_tools(monkeypatch):
    """spy 进 build_safety_tools，把 sink + tools 暴露给测试用例。"""
    captured: dict[str, Any] = {}

    def spy(loader, sink):
        tools = _real_build_safety_tools(loader, sink)
        captured["sink"] = sink
        captured["by_name"] = {t.name: t for t in tools}
        return tools

    monkeypatch.setattr(agent_mod, "build_safety_tools", spy)
    return captured


async def test_happy_path(monkeypatch, settings, skill_loader, spy_build_tools) -> None:
    """模拟 Agent 调用 submit_safety_report，最终返回报告 + 统计。"""

    async def fake_query(*, prompt, options, transport=None):
        # 模拟 Agent 调 submit
        submit = spy_build_tools["by_name"]["submit_safety_report"]
        await submit.handler({"report_json": json.dumps(VALID_REPORT, ensure_ascii=False)})
        yield _make_result_message()

    monkeypatch.setattr(agent_mod, "query", fake_query)

    report, stats = await agent_mod.analyze_image(
        image_bytes=b"fake-jpeg",
        settings=settings,
        skill_loader=skill_loader,
    )
    assert report.findings[0].check_id == "B01"
    assert stats.input_tokens == 1000
    assert stats.output_tokens == 200
    assert stats.cost_usd == pytest.approx(0.012)


async def test_agent_did_not_submit_raises(
    monkeypatch, settings, skill_loader, spy_build_tools
) -> None:
    """Agent 走完整个 stream 却没调 submit → LLMCallError。"""

    async def fake_query(*, prompt, options, transport=None):
        # 不调任何工具，直接 yield 结束
        yield _make_result_message()

    monkeypatch.setattr(agent_mod, "query", fake_query)

    with pytest.raises(LLMCallError) as exc:
        await agent_mod.analyze_image(
            image_bytes=b"x", settings=settings, skill_loader=skill_loader
        )
    assert "submit_safety_report" in str(exc.value)


async def test_sdk_error_wrapped(monkeypatch, settings, skill_loader, spy_build_tools) -> None:
    """SDK 抛 ClaudeSDKError → 包装成 LLMCallError。"""
    from claude_agent_sdk import ClaudeSDKError

    async def fake_query(*, prompt, options, transport=None):
        raise ClaudeSDKError("simulated CLI failure")
        yield  # 让函数成为 async generator（不会跑到这里）

    monkeypatch.setattr(agent_mod, "query", fake_query)

    with pytest.raises(LLMCallError) as exc:
        await agent_mod.analyze_image(
            image_bytes=b"x", settings=settings, skill_loader=skill_loader
        )
    assert "simulated CLI failure" in str(exc.value)


async def test_timeout_raises_llm_timeout(
    monkeypatch, skill_loader, spy_build_tools
) -> None:
    """流跑得比 agent_timeout_seconds 慢 → LLMTimeoutError。"""
    tight_settings = Settings(agent_timeout_seconds=1, safety_skills_root=SKILLS_ROOT)

    async def slow_query(*, prompt, options, transport=None):
        await asyncio.sleep(10)
        yield _make_result_message()

    monkeypatch.setattr(agent_mod, "query", slow_query)

    with pytest.raises(LLMTimeoutError):
        await agent_mod.analyze_image(
            image_bytes=b"x", settings=tight_settings, skill_loader=skill_loader
        )


async def test_cli_path_forwarded_to_options(
    monkeypatch, skill_loader, spy_build_tools
) -> None:
    """ClaudeAgentOptions 必须显式拿到 settings.claude_cli_path。

    动机：v2 Agent SDK 之前不传 cli_path 会回退到 SDK bundled CLI，
    在某些版本组合下吐 'error result: success' 直接挂掉生产
    （PR #10 修复）。本测试是回归保护 —— 谁删 / 改 cli_path 行立刻红。

    断言点：
    1. options.cli_path 与 settings.claude_cli_path 字符串相等
    2. options.model 与 settings.agent_model 一致（顺带防误删邻近行）
    """
    captured: dict[str, Any] = {}
    custom_cli = "/opt/claude/bin/claude-custom"
    custom_settings = Settings(
        agent_timeout_seconds=5,
        safety_skills_root=SKILLS_ROOT,
        claude_cli_path=custom_cli,
    )

    async def fake_query(*, prompt, options, transport=None):
        captured["options"] = options
        submit = spy_build_tools["by_name"]["submit_safety_report"]
        await submit.handler({"report_json": json.dumps(VALID_REPORT, ensure_ascii=False)})
        yield _make_result_message()

    monkeypatch.setattr(agent_mod, "query", fake_query)

    await agent_mod.analyze_image(
        image_bytes=b"x", settings=custom_settings, skill_loader=skill_loader
    )

    opts = captured["options"]
    assert opts.cli_path == custom_cli, (
        "ClaudeAgentOptions.cli_path 必须等于 settings.claude_cli_path —— "
        "丢失这个绑定会让 v2 退回 SDK bundled CLI 触发生产 'error result: success'"
    )
    assert opts.model == custom_settings.agent_model


async def test_load_scenario_skill_no_longer_in_allowed_tools(
    monkeypatch, settings, skill_loader, spy_build_tools
) -> None:
    """回归保护：load_scenario_skill 工具已下线（12 个场景全部 inline 进 system
    prompt）。allowed_tools 里不应再出现这个 FQN，否则模型可能误以为还能调它。
    """
    captured: dict[str, Any] = {}

    async def fake_query(*, prompt, options, transport=None):
        captured["options"] = options
        submit = spy_build_tools["by_name"]["submit_safety_report"]
        await submit.handler({"report_json": json.dumps(VALID_REPORT, ensure_ascii=False)})
        yield _make_result_message()

    monkeypatch.setattr(agent_mod, "query", fake_query)

    await agent_mod.analyze_image(
        image_bytes=b"x", settings=settings, skill_loader=skill_loader
    )

    allowed = captured["options"].allowed_tools
    assert "Read" in allowed
    assert any(t.endswith("submit_safety_report") for t in allowed)
    assert not any("load_scenario_skill" in t for t in allowed), (
        f"load_scenario_skill 应已从 allowed_tools 移除，但发现: {allowed}"
    )


async def test_scenarios_loaded_no_longer_tracked_via_tool(
    monkeypatch, settings, skill_loader, spy_build_tools
) -> None:
    """load_scenario_skill 下线后，AgentRunStats.scenarios_loaded 保持空。
    场景命中信息改由 service 层从 report.report_meta.scene_detected 取，
    不再由 agent 在 _drain 里累计。
    """
    async def fake_query(*, prompt, options, transport=None):
        submit = spy_build_tools["by_name"]["submit_safety_report"]
        await submit.handler({"report_json": json.dumps(VALID_REPORT, ensure_ascii=False)})
        yield _make_result_message()

    monkeypatch.setattr(agent_mod, "query", fake_query)

    _, stats = await agent_mod.analyze_image(
        image_bytes=b"x", settings=settings, skill_loader=skill_loader
    )
    assert stats.scenarios_loaded == []  # agent 不再从 tool 调用累计场景
    assert stats.tool_calls == 0  # submit 是 spy 直接调的，不经过 stream


async def test_cache_tokens_captured_from_usage(
    monkeypatch, settings, skill_loader, spy_build_tools
) -> None:
    """ResultMessage.usage 含 cache_read_input_tokens / cache_creation_input_tokens
    时，AgentRunStats 必须分别落到 cache_read_tokens / cache_creation_tokens。

    动机：prompt caching 开启后，要靠这两个字段独立衡量"省了多少 input cost / 多少
    被重新写入"。只看 total_cost_usd 看不出来。
    """

    async def fake_query(*, prompt, options, transport=None):
        submit = spy_build_tools["by_name"]["submit_safety_report"]
        await submit.handler({"report_json": json.dumps(VALID_REPORT, ensure_ascii=False)})
        yield _make_result_message(
            input_tokens=300,
            output_tokens=500,
            cache_read_input_tokens=8500,
            cache_creation_input_tokens=1200,
        )

    monkeypatch.setattr(agent_mod, "query", fake_query)

    _, stats = await agent_mod.analyze_image(
        image_bytes=b"x", settings=settings, skill_loader=skill_loader
    )
    assert stats.input_tokens == 300
    assert stats.output_tokens == 500
    assert stats.cache_read_tokens == 8500
    assert stats.cache_creation_tokens == 1200


async def test_tool_call_timings_capture_dispatched_ms_per_tool(
    monkeypatch, settings, skill_loader, spy_build_tools
) -> None:
    """tool_call_timings 必须为每个 ToolUseBlock 记一条 {seq,name,dispatched_ms}。

    断言：
    - 序号 seq 与 stats.tool_calls 累计严格对齐
    - 同一 AssistantMessage 内的多个 tool 共享 dispatched_ms（SDK 一帧批发）
    - 后续 AssistantMessage 的 tool 拿到的 dispatched_ms 严格更大
    - 工具名做短名化（去掉 mcp__safety__ 前缀）
    - load_scenario_skill 已下线，scenario_id 字段也已下线（一并验证不再注入）
    """
    import asyncio as _asyncio

    from claude_agent_sdk import AssistantMessage, ToolUseBlock

    async def fake_query(*, prompt, options, transport=None):
        # 第一帧：同时 dispatch 两个 Read（构造同帧批发场景）
        yield AssistantMessage(
            content=[
                ToolUseBlock(id="t1", name="Read", input={"file_path": "/tmp/a.jpg"}),
                ToolUseBlock(id="t2", name="Read", input={"file_path": "/tmp/b.jpg"}),
            ],
            model="claude-opus-4-7",
        )
        # 让壁钟前进，确保下一帧的 dispatched_ms 严格大于上一帧
        await _asyncio.sleep(0.05)
        # 第二帧：单个 submit
        yield AssistantMessage(
            content=[
                ToolUseBlock(
                    id="t3",
                    name="mcp__safety__submit_safety_report",
                    input={"report_json": "{}"},
                )
            ],
            model="claude-opus-4-7",
        )
        # submit 走 spy（不经过 stream，所以不进 timings）
        submit = spy_build_tools["by_name"]["submit_safety_report"]
        await submit.handler({"report_json": json.dumps(VALID_REPORT, ensure_ascii=False)})
        yield _make_result_message()

    monkeypatch.setattr(agent_mod, "query", fake_query)

    _, stats = await agent_mod.analyze_image(
        image_bytes=b"x", settings=settings, skill_loader=skill_loader
    )

    assert stats.tool_calls == 3  # 2 Read + 1 submit-via-stream（spy 那次不计）
    assert len(stats.tool_call_timings) == 3

    t = stats.tool_call_timings
    # seq 严格 1..N
    assert [e["seq"] for e in t] == [1, 2, 3]
    # 名字短化
    assert t[0]["name"] == "Read"
    assert t[1]["name"] == "Read"
    assert t[2]["name"] == "submit_safety_report"  # mcp__safety__ 前缀已剥
    # 同一帧两个 tool 共享 dispatched_ms
    assert t[0]["dispatched_ms"] == t[1]["dispatched_ms"]
    # 下一帧严格更大（>= sleep 的 50ms）
    assert t[2]["dispatched_ms"] > t[0]["dispatched_ms"]
    assert t[2]["dispatched_ms"] - t[0]["dispatched_ms"] >= 40  # 留 10ms 余量
    # scenario_id 字段已下线，不再附在任何工具上
    for entry in t:
        assert "scenario_id" not in entry
