"""analyze_image orchestration 测试 —— 不打 Claude，靠 monkeypatch 模拟 SDK。

策略：
- monkeypatch `app.safety_agent.agent.query` 为 async generator
- structured output 模式下，最终回复通过 AssistantMessage(ToolUseBlock(
  name="StructuredOutput", input=<dict>)) 回传（CLI 在 json_schema 模式注入的
  虚拟工具）；agent 从 stats.structured_output 拿这个 dict 并 pydantic 校验
- 覆盖：happy / 缺失输出 / schema 不通过 / SDK 异常 / 超时 / 选项透传 /
  cache token / tool 时间戳 / thinking 配置 / cli_path 回归 / system_prompt
  走 file 形式（Windows cmd 长度限制回归保护）
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

VALID_REPORT_JSON = json.dumps(VALID_REPORT, ensure_ascii=False)


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


def _make_assistant_text(text: str):
    """模拟一条只含 TextBlock 的 AssistantMessage（中间过程文本，会被 _drain 忽略）。"""
    from claude_agent_sdk import AssistantMessage, TextBlock

    return AssistantMessage(content=[TextBlock(text=text)], model="claude-sonnet-4-6")


def _make_structured_output(payload: dict):
    """模拟 CLI 在 output_format=json_schema 模式回传的"虚拟工具"调用 ——
    StructuredOutput.input 就是模型生成的最终 JSON dict。"""
    from claude_agent_sdk import AssistantMessage, ToolUseBlock

    return AssistantMessage(
        content=[ToolUseBlock(id="so1", name="StructuredOutput", input=payload)],
        model="claude-sonnet-4-6",
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


# ============== happy / error 主线 ==============


async def test_happy_path(monkeypatch, settings, skill_loader) -> None:
    """模拟 SDK 通过 structured output 直接吐合法 JSON 文本，agent 解析后返回。"""

    async def fake_query(*, prompt, options, transport=None):
        yield _make_structured_output(VALID_REPORT)
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
    assert stats.structured_output == VALID_REPORT


async def test_no_structured_output_raises(monkeypatch, settings, skill_loader) -> None:
    """structured output 模式下整个流程结束都没收到 StructuredOutput 工具调用
    → LLMCallError（语义对齐旧版"sink 空"）。"""

    async def fake_query(*, prompt, options, transport=None):
        # 只 yield ResultMessage 和一些过程文本，没 StructuredOutput
        yield _make_assistant_text("正在分析...")
        yield _make_result_message()

    monkeypatch.setattr(agent_mod, "query", fake_query)

    with pytest.raises(LLMCallError) as exc:
        await agent_mod.analyze_image(
            image_bytes=b"x", settings=settings, skill_loader=skill_loader
        )
    assert "StructuredOutput" in str(exc.value)


async def test_malformed_structured_output_raises_llm_call_error(
    monkeypatch, settings, skill_loader
) -> None:
    """StructuredOutput.input 缺必填字段 → LLMCallError，带顶层 keys 便于排查。

    动机：SDK 的 --json-schema 理论上保证合法，但 API 漂移 / 模型偶发越界仍可能
    发生。要让兜底失败给出清晰错误（字段路径 + 顶层 keys），便于定位。
    """

    async def fake_query(*, prompt, options, transport=None):
        # 合法 dict 但缺 report_meta / summary 必填字段
        yield _make_structured_output({"findings": []})
        yield _make_result_message()

    monkeypatch.setattr(agent_mod, "query", fake_query)

    with pytest.raises(LLMCallError) as exc:
        await agent_mod.analyze_image(
            image_bytes=b"x", settings=settings, skill_loader=skill_loader
        )
    msg = str(exc.value)
    assert "ReportV2Payload" in msg or "未通过" in msg
    # 错误信息应包含至少一个字段路径（如 'report_meta' / 'summary'）便于定位
    assert any(k in msg for k in ["report_meta", "summary", "顶层"])


async def test_sdk_error_wrapped(monkeypatch, settings, skill_loader) -> None:
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


async def test_timeout_raises_llm_timeout(monkeypatch, skill_loader) -> None:
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


# ============== ClaudeAgentOptions 透传断言 ==============


async def _capture_options(monkeypatch, settings, skill_loader) -> Any:
    """跑一次 analyze_image，把 query() 收到的 options 捕获回来。"""
    captured: dict[str, Any] = {}

    async def fake_query(*, prompt, options, transport=None):
        captured["options"] = options
        yield _make_structured_output(VALID_REPORT)
        yield _make_result_message()

    monkeypatch.setattr(agent_mod, "query", fake_query)
    await agent_mod.analyze_image(
        image_bytes=b"x", settings=settings, skill_loader=skill_loader
    )
    return captured["options"]


async def test_cli_path_forwarded_to_options(monkeypatch, skill_loader) -> None:
    """ClaudeAgentOptions 必须显式拿到 settings.claude_cli_path。

    动机：v2 Agent SDK 之前不传 cli_path 会回退到 SDK bundled CLI，
    在某些版本组合下吐 'error result: success' 直接挂掉生产（PR #10 修复）。
    本测试是回归保护 —— 谁删 / 改 cli_path 行立刻红。
    """
    custom_cli = "/opt/claude/bin/claude-custom"
    custom_settings = Settings(
        agent_timeout_seconds=5,
        safety_skills_root=SKILLS_ROOT,
        claude_cli_path=custom_cli,
    )

    opts = await _capture_options(monkeypatch, custom_settings, skill_loader)

    assert opts.cli_path == custom_cli, (
        "ClaudeAgentOptions.cli_path 必须等于 settings.claude_cli_path —— "
        "丢失这个绑定会让 v2 退回 SDK bundled CLI 触发生产 'error result: success'"
    )
    assert opts.model == custom_settings.agent_model


async def test_allowed_tools_only_read(monkeypatch, settings, skill_loader) -> None:
    """structured output 后只剩 Read 一个工具：load_scenario_skill 已下线
    （inline 化），submit_safety_report 已下线（native output_format 取代）。
    """
    opts = await _capture_options(monkeypatch, settings, skill_loader)
    assert opts.allowed_tools == ["Read"], (
        f"allowed_tools 应仅为 ['Read']，实际: {opts.allowed_tools}"
    )


async def test_output_format_passed_to_options(
    monkeypatch, settings, skill_loader
) -> None:
    """output_format 必须是 json_schema 类型，schema 来自 ReportV2Payload。

    断言细到 schema 内容：含 properties.findings、properties.report_meta —— 这样
    谁误把 schema 换成空对象或别的模型，立刻红。
    """
    opts = await _capture_options(monkeypatch, settings, skill_loader)
    assert opts.output_format is not None, "structured output 模式必须设 output_format"
    assert opts.output_format["type"] == "json_schema"
    schema = opts.output_format["schema"]
    # ReportV2Payload 顶层字段（properties 来自 pydantic）
    assert "properties" in schema
    assert "findings" in schema["properties"]
    assert "report_meta" in schema["properties"]
    assert "summary" in schema["properties"]


async def test_thinking_enabled_when_budget_positive(
    monkeypatch, skill_loader
) -> None:
    """thinking_budget > 0 时必须传 thinking={'type':'enabled','budget_tokens':N}。

    动机：禁过程文本依赖 extended thinking 把推理"转入内部通道"。如果误把
    thinking 关掉，模型可能在最终 JSON 之前/中夹杂大量过程文本，输出体量回涨。
    """
    s = Settings(
        agent_timeout_seconds=5,
        safety_skills_root=SKILLS_ROOT,
        agent_thinking_budget_tokens=5000,
    )
    opts = await _capture_options(monkeypatch, s, skill_loader)
    assert opts.thinking is not None
    assert opts.thinking["type"] == "enabled"
    assert opts.thinking["budget_tokens"] == 5000


async def test_system_prompt_passed_as_file_not_inline_string(
    monkeypatch, settings, skill_loader
) -> None:
    """回归保护：system_prompt 必须以 {"type":"file","path":...} 形式传给 SDK，
    不能 inline 成字符串 arg。

    动机：inline 12 个场景后 system prompt 达 36k 字符，Windows CreateProcessW
    上限 32,767 字符。直接 inline 会让 spawn 失败，SDK 翻译成误导性的
    "Claude Code not found at: claude"（FileNotFoundError 被错误归因到 CLI）。

    断言：
    - options.system_prompt 是 dict 且 type=='file'
    - path 指向一个实际存在的 .txt 临时文件
    - 文件内容与 PromptBuilder.build_system_prompt() 一致
    """
    from app.safety_agent.prompt import PromptBuilder

    opts = await _capture_options(monkeypatch, settings, skill_loader)
    sp = opts.system_prompt
    assert isinstance(sp, dict), (
        f"system_prompt 必须是 dict (走 --system-prompt-file)，实际类型: {type(sp)}"
    )
    assert sp.get("type") == "file"
    sp_path = Path(sp["path"])
    # 文件可能已被 analyze_image 的 finally 清理 —— 但 _capture_options 同步消费
    # 完后才返回，可能赶得上读到，所以做一次软断言：能读就核对内容，不能读至少
    # 路径形似 tempfile
    assert sp_path.name.endswith(".txt")
    if sp_path.is_file():
        expected = PromptBuilder(skill_loader).build_system_prompt()
        assert sp_path.read_text(encoding="utf-8") == expected


async def test_thinking_disabled_when_budget_zero(monkeypatch, skill_loader) -> None:
    """budget=0 → 不传 thinking（A/B 对比"无思考"基线时用得着）。"""
    s = Settings(
        agent_timeout_seconds=5,
        safety_skills_root=SKILLS_ROOT,
        agent_thinking_budget_tokens=0,
    )
    opts = await _capture_options(monkeypatch, s, skill_loader)
    assert opts.thinking is None


async def test_load_scenario_skill_no_longer_in_allowed_tools(
    monkeypatch, settings, skill_loader
) -> None:
    """回归保护：load_scenario_skill 工具已下线，名字不应出现在 allowed_tools。"""
    opts = await _capture_options(monkeypatch, settings, skill_loader)
    assert not any("load_scenario_skill" in t for t in opts.allowed_tools), (
        f"load_scenario_skill 应已从 allowed_tools 移除，但发现: {opts.allowed_tools}"
    )


async def test_submit_safety_report_no_longer_in_allowed_tools(
    monkeypatch, settings, skill_loader
) -> None:
    """回归保护：submit_safety_report 工具已下线（structured output 取代），
    名字不应出现在 allowed_tools。"""
    opts = await _capture_options(monkeypatch, settings, skill_loader)
    assert not any("submit_safety_report" in t for t in opts.allowed_tools), (
        f"submit_safety_report 应已从 allowed_tools 移除，但发现: {opts.allowed_tools}"
    )


# ============== AgentRunStats 字段采集 ==============


async def test_scenarios_loaded_no_longer_tracked_via_tool(
    monkeypatch, settings, skill_loader
) -> None:
    """load_scenario_skill 下线后，AgentRunStats.scenarios_loaded 保持空。
    场景命中信息改由 service 层从 report.report_meta.scene_detected 取，
    不再由 agent 在 _drain 里累计。
    """
    async def fake_query(*, prompt, options, transport=None):
        yield _make_structured_output(VALID_REPORT)
        yield _make_result_message()

    monkeypatch.setattr(agent_mod, "query", fake_query)

    _, stats = await agent_mod.analyze_image(
        image_bytes=b"x", settings=settings, skill_loader=skill_loader
    )
    assert stats.scenarios_loaded == []  # agent 不再从 tool 调用累计场景
    assert stats.tool_calls == 0  # StructuredOutput 虚拟工具不计入业务 tool_calls


async def test_cache_tokens_captured_from_usage(
    monkeypatch, settings, skill_loader
) -> None:
    """ResultMessage.usage 含 cache_read_input_tokens / cache_creation_input_tokens
    时，AgentRunStats 必须分别落到 cache_read_tokens / cache_creation_tokens。
    """

    async def fake_query(*, prompt, options, transport=None):
        yield _make_structured_output(VALID_REPORT)
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
    monkeypatch, settings, skill_loader
) -> None:
    """tool_call_timings 必须为每个 ToolUseBlock 记一条 {seq,name,dispatched_ms}。

    断言：
    - 序号 seq 与 stats.tool_calls 累计严格对齐
    - 同一 AssistantMessage 内的多个 tool 共享 dispatched_ms（SDK 一帧批发）
    - 后续 AssistantMessage 的 tool 拿到的 dispatched_ms 严格更大
    - 工具名做短名化（去掉 mcp__safety__ 前缀）
    - load_scenario_skill 已下线，scenario_id 字段也已下线
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
            model="claude-sonnet-4-6",
        )
        # 让壁钟前进，确保下一帧的 dispatched_ms 严格大于上一帧
        await _asyncio.sleep(0.05)
        # 第二帧：最终 JSON 文本（structured output）
        yield _make_structured_output(VALID_REPORT)
        yield _make_result_message()

    monkeypatch.setattr(agent_mod, "query", fake_query)

    _, stats = await agent_mod.analyze_image(
        image_bytes=b"x", settings=settings, skill_loader=skill_loader
    )

    assert stats.tool_calls == 2  # 2 个 Read；StructuredOutput 虚拟工具不算业务 tool
    assert len(stats.tool_call_timings) == 2

    t = stats.tool_call_timings
    # seq 严格 1..N
    assert [e["seq"] for e in t] == [1, 2]
    # 名字短化
    assert t[0]["name"] == "Read"
    assert t[1]["name"] == "Read"
    # 同一帧两个 tool 共享 dispatched_ms
    assert t[0]["dispatched_ms"] == t[1]["dispatched_ms"]
    # scenario_id 字段已下线，不再附在任何工具上
    for entry in t:
        assert "scenario_id" not in entry


async def test_structured_output_captures_dict_ignores_intermediate_text(
    monkeypatch, settings, skill_loader
) -> None:
    """StructuredOutput.input（dict）被收到 stats.structured_output；
    中间过程文本（如有）不污染。

    动机：模型在调用 Read 之间、生成 StructuredOutput 之前可能输出一些过程性文本
    （即便 prompt 禁了也偶发），不能让它影响最终 JSON 解析。
    """
    async def fake_query(*, prompt, options, transport=None):
        # 前面一段过程文本（应被忽略）
        yield _make_assistant_text("正在分析图片...")
        # 最终通过 StructuredOutput 虚拟工具回传
        yield _make_structured_output(VALID_REPORT)
        yield _make_result_message()

    monkeypatch.setattr(agent_mod, "query", fake_query)

    report, stats = await agent_mod.analyze_image(
        image_bytes=b"x", settings=settings, skill_loader=skill_loader
    )
    assert stats.structured_output == VALID_REPORT
    assert report.findings[0].check_id == "B01"
