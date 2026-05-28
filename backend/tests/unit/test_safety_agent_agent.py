"""analyze_image 两阶段 orchestration 测试 —— 不打 Claude，靠 monkeypatch 模拟 SDK。

v4 两阶段架构：
- Stage 1：用 submit_scene_detection 工具识别场景，sink: list[list[str]]
- Stage 2：用 submit_safety_report 工具提交完整报告，sink: list[ReportV2Payload]

策略：
- monkeypatch `app.safety_agent.agent.build_scene_detection_tool` 和
  `build_safety_tools` 各捕获自己的 sink/tools 到 fixture 暴露的字典
- monkeypatch `app.safety_agent.agent.query` 为 async generator 工厂：每被调一次
  返回不同的 stream（stage 1 的或 stage 2 的）
- 覆盖：happy / stage1 失败降级 / stage2 异常 / 超时 / 选项透传 / cache token /
  tool 时间戳 / system_prompt 走 file / thinking 配置等
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
from app.safety_agent.tools import (
    build_safety_tools as _real_build_safety_tools,
    build_scene_detection_tool as _real_build_scene_detection_tool,
)

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
    total_cost_usd: float = 0.012,
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
        total_cost_usd=total_cost_usd,
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
    """两阶段模式默认 settings —— 本文件大多数测试用例针对 v4 两阶段架构。

    生产默认是单阶段（agent_use_two_stage=False），见下方 single_stage_settings。
    """
    return Settings(
        agent_timeout_seconds=5,
        safety_skills_root=SKILLS_ROOT,
        agent_use_two_stage=True,
    )


@pytest.fixture
def single_stage_settings() -> Settings:
    """生产默认 settings —— 单阶段（v3 行为）。"""
    return Settings(
        agent_timeout_seconds=5,
        safety_skills_root=SKILLS_ROOT,
        agent_use_two_stage=False,
    )


@pytest.fixture
def spy_tools(monkeypatch):
    """spy 进两个工具工厂，把 sink + tools 暴露给测试用例。

    返回字典：
    - "scene_sink": list[list[str]]，被 stage 1 工具填充
    - "report_sink": list[ReportV2Payload]，被 stage 2 工具填充
    - "scene_tool": stage 1 的 submit_scene_detection 工具实例
    - "report_tool": stage 2 的 submit_safety_report 工具实例
    """
    captured: dict[str, Any] = {}

    def spy_detect(loader, sink):
        tools = _real_build_scene_detection_tool(loader, sink)
        captured["scene_sink"] = sink
        captured["scene_tool"] = tools[0]
        return tools

    def spy_safety(loader, sink):
        tools = _real_build_safety_tools(loader, sink)
        captured["report_sink"] = sink
        captured["report_tool"] = tools[0]
        return tools

    monkeypatch.setattr(agent_mod, "build_scene_detection_tool", spy_detect)
    monkeypatch.setattr(agent_mod, "build_safety_tools", spy_safety)
    return captured


def _fake_query_factory(stage1_stream, stage2_stream, captured_options: list | None = None):
    """工厂：返回的 query 函数被调第 N 次时使用第 N 个 stream。

    captured_options: 如果给了 list，每次调用把 options append 进去（顺序：stage1 → stage2）
    """
    call_count = {"n": 0}
    streams = [stage1_stream, stage2_stream]

    async def fake_query(*, prompt, options, transport=None):
        idx = call_count["n"]
        call_count["n"] += 1
        if captured_options is not None:
            captured_options.append(options)
        # streams[idx] 是一个 callable 返回 async generator
        gen = streams[idx]()
        async for msg in gen:
            yield msg

    return fake_query


# ========== happy path ==========


async def test_happy_path_two_stage(monkeypatch, settings, skill_loader, spy_tools) -> None:
    """模拟 stage 1 返回 [S03] → stage 2 用 S03 子集 prompt 跑出 report。"""

    def stage1_stream():
        async def gen():
            scene_tool = spy_tools["scene_tool"]
            await scene_tool.handler({"scenes": ["S03", "S05"]})
            yield _make_result_message(
                input_tokens=100, output_tokens=20, total_cost_usd=0.005
            )
        return gen()

    def stage2_stream():
        async def gen():
            report_tool = spy_tools["report_tool"]
            await report_tool.handler(
                {"report_json": json.dumps(VALID_REPORT, ensure_ascii=False)}
            )
            yield _make_result_message(
                input_tokens=900, output_tokens=180, total_cost_usd=0.007
            )
        return gen()

    monkeypatch.setattr(
        agent_mod, "query", _fake_query_factory(stage1_stream, stage2_stream)
    )

    report, stats = await agent_mod.analyze_image(
        image_bytes=b"fake-jpeg", settings=settings, skill_loader=skill_loader
    )

    # Stage 2 的 report 被返回
    assert report.findings[0].check_id == "B01"
    # stage 1 识别出的场景保存到 stats.scenarios_loaded
    assert stats.scenarios_loaded == ["S03", "S05"]
    # token 跨阶段累加
    assert stats.input_tokens == 100 + 900
    assert stats.output_tokens == 20 + 180
    assert stats.cost_usd == pytest.approx(0.005 + 0.007)


async def test_stage1_unknown_ids_filtered(
    monkeypatch, settings, skill_loader, spy_tools
) -> None:
    """Stage 1 返回部分非法 ID（如 S99）→ 工具过滤后只保留合法的；stage 2 用过滤后列表。"""

    def stage1_stream():
        async def gen():
            scene_tool = spy_tools["scene_tool"]
            # S99 不存在，应被过滤
            await scene_tool.handler({"scenes": ["S03", "S99", "S05"]})
            yield _make_result_message()
        return gen()

    def stage2_stream():
        async def gen():
            report_tool = spy_tools["report_tool"]
            await report_tool.handler(
                {"report_json": json.dumps(VALID_REPORT, ensure_ascii=False)}
            )
            yield _make_result_message()
        return gen()

    monkeypatch.setattr(
        agent_mod, "query", _fake_query_factory(stage1_stream, stage2_stream)
    )

    _, stats = await agent_mod.analyze_image(
        image_bytes=b"x", settings=settings, skill_loader=skill_loader
    )
    assert stats.scenarios_loaded == ["S03", "S05"]  # S99 被工具过滤


# ========== stage1 失败降级路径 ==========


async def test_stage1_no_submit_falls_back_to_all_scenarios(
    monkeypatch, settings, skill_loader, spy_tools
) -> None:
    """Stage 1 结束但模型没调 submit_scene_detection → stage 2 应走全 12 个场景兜底
    （即 scenarios_loaded 为空、不报错、stage 2 仍正常跑出报告）。
    """

    def stage1_stream():
        async def gen():
            # 不调任何工具
            yield _make_result_message()
        return gen()

    def stage2_stream():
        async def gen():
            report_tool = spy_tools["report_tool"]
            await report_tool.handler(
                {"report_json": json.dumps(VALID_REPORT, ensure_ascii=False)}
            )
            yield _make_result_message()
        return gen()

    monkeypatch.setattr(
        agent_mod, "query", _fake_query_factory(stage1_stream, stage2_stream)
    )

    report, stats = await agent_mod.analyze_image(
        image_bytes=b"x", settings=settings, skill_loader=skill_loader
    )
    assert report.findings[0].check_id == "B01"  # stage 2 仍成功
    assert stats.scenarios_loaded == []  # 没识别出场景


async def test_stage1_sdk_error_falls_back(
    monkeypatch, settings, skill_loader, spy_tools
) -> None:
    """Stage 1 抛 ClaudeSDKError → 降级到全 inline 走 stage 2，整次不挂。"""
    from claude_agent_sdk import ClaudeSDKError

    def stage1_stream():
        async def gen():
            raise ClaudeSDKError("simulated stage1 failure")
            yield  # 让函数成为 async generator
        return gen()

    def stage2_stream():
        async def gen():
            report_tool = spy_tools["report_tool"]
            await report_tool.handler(
                {"report_json": json.dumps(VALID_REPORT, ensure_ascii=False)}
            )
            yield _make_result_message()
        return gen()

    monkeypatch.setattr(
        agent_mod, "query", _fake_query_factory(stage1_stream, stage2_stream)
    )

    report, stats = await agent_mod.analyze_image(
        image_bytes=b"x", settings=settings, skill_loader=skill_loader
    )
    assert report.findings[0].check_id == "B01"
    assert stats.scenarios_loaded == []


# ========== stage2 异常路径 ==========


async def test_stage2_did_not_submit_raises(
    monkeypatch, settings, skill_loader, spy_tools
) -> None:
    """Stage 2 没调 submit_safety_report → LLMCallError。"""

    def stage1_stream():
        async def gen():
            await spy_tools["scene_tool"].handler({"scenes": ["S03"]})
            yield _make_result_message()
        return gen()

    def stage2_stream():
        async def gen():
            yield _make_result_message()  # 不调任何工具
        return gen()

    monkeypatch.setattr(
        agent_mod, "query", _fake_query_factory(stage1_stream, stage2_stream)
    )

    with pytest.raises(LLMCallError) as exc:
        await agent_mod.analyze_image(
            image_bytes=b"x", settings=settings, skill_loader=skill_loader
        )
    assert "submit_safety_report" in str(exc.value)


async def test_stage2_sdk_error_wrapped(
    monkeypatch, settings, skill_loader, spy_tools
) -> None:
    """Stage 2 SDK 异常 → 包装成 LLMCallError。"""
    from claude_agent_sdk import ClaudeSDKError

    def stage1_stream():
        async def gen():
            await spy_tools["scene_tool"].handler({"scenes": ["S03"]})
            yield _make_result_message()
        return gen()

    def stage2_stream():
        async def gen():
            raise ClaudeSDKError("simulated stage2 failure")
            yield
        return gen()

    monkeypatch.setattr(
        agent_mod, "query", _fake_query_factory(stage1_stream, stage2_stream)
    )

    with pytest.raises(LLMCallError) as exc:
        await agent_mod.analyze_image(
            image_bytes=b"x", settings=settings, skill_loader=skill_loader
        )
    assert "simulated stage2 failure" in str(exc.value)


async def test_overall_timeout_raises_llm_timeout(
    monkeypatch, skill_loader, spy_tools
) -> None:
    """两阶段总耗时超 agent_timeout_seconds → LLMTimeoutError。"""
    tight_settings = Settings(
        agent_timeout_seconds=1,
        safety_skills_root=SKILLS_ROOT,
        agent_use_two_stage=True,
    )

    def stage1_stream():
        async def gen():
            await spy_tools["scene_tool"].handler({"scenes": ["S03"]})
            yield _make_result_message()
        return gen()

    def stage2_stream():
        async def gen():
            await asyncio.sleep(10)
            yield _make_result_message()
        return gen()

    monkeypatch.setattr(
        agent_mod, "query", _fake_query_factory(stage1_stream, stage2_stream)
    )

    with pytest.raises(LLMTimeoutError):
        await agent_mod.analyze_image(
            image_bytes=b"x", settings=tight_settings, skill_loader=skill_loader
        )


# ========== ClaudeAgentOptions 透传断言 ==========


async def _capture_both_options(
    monkeypatch, settings, skill_loader, spy_tools
) -> list[Any]:
    """跑一次 happy path，捕获 stage 1 + stage 2 两次 query 的 options。"""
    captured_opts: list[Any] = []

    def stage1_stream():
        async def gen():
            await spy_tools["scene_tool"].handler({"scenes": ["S03"]})
            yield _make_result_message()
        return gen()

    def stage2_stream():
        async def gen():
            await spy_tools["report_tool"].handler(
                {"report_json": json.dumps(VALID_REPORT, ensure_ascii=False)}
            )
            yield _make_result_message()
        return gen()

    monkeypatch.setattr(
        agent_mod, "query",
        _fake_query_factory(stage1_stream, stage2_stream, captured_options=captured_opts),
    )
    await agent_mod.analyze_image(
        image_bytes=b"x", settings=settings, skill_loader=skill_loader
    )
    return captured_opts


async def test_cli_path_forwarded_to_options(monkeypatch, skill_loader, spy_tools) -> None:
    """两个 stage 的 ClaudeAgentOptions 都必须显式拿到 settings.claude_cli_path。

    动机：见 PR #10 修复（SDK bundled CLI 兼容性差）。两阶段架构里两次 query
    都要带 cli_path，缺一个就翻车 → 这里同时断言两次。
    """
    custom_cli = "/opt/claude/bin/claude-custom"
    custom_settings = Settings(
        agent_timeout_seconds=5,
        safety_skills_root=SKILLS_ROOT,
        claude_cli_path=custom_cli,
        agent_use_two_stage=True,
    )
    opts = await _capture_both_options(monkeypatch, custom_settings, skill_loader, spy_tools)
    assert len(opts) == 2, "应该跑两个 query 调用（stage 1 + stage 2）"
    for i, o in enumerate(opts):
        assert o.cli_path == custom_cli, f"stage{i+1} options.cli_path 必须等于 settings.claude_cli_path"
        assert o.model == custom_settings.agent_model


async def test_stage1_allowed_tools_only_read_and_detection(
    monkeypatch, settings, skill_loader, spy_tools
) -> None:
    """Stage 1 allowed_tools = ['Read', mcp__safety__submit_scene_detection]，
    不应包含 submit_safety_report（stage 2 才用）。"""
    opts = await _capture_both_options(monkeypatch, settings, skill_loader, spy_tools)
    stage1_allowed = opts[0].allowed_tools
    assert "Read" in stage1_allowed
    assert any("submit_scene_detection" in t for t in stage1_allowed)
    assert not any("submit_safety_report" in t for t in stage1_allowed)


async def test_stage2_allowed_tools_only_read_and_safety(
    monkeypatch, settings, skill_loader, spy_tools
) -> None:
    """Stage 2 allowed_tools = ['Read', mcp__safety__submit_safety_report]，
    不应包含 submit_scene_detection（stage 1 才用）。"""
    opts = await _capture_both_options(monkeypatch, settings, skill_loader, spy_tools)
    stage2_allowed = opts[1].allowed_tools
    assert "Read" in stage2_allowed
    assert any("submit_safety_report" in t for t in stage2_allowed)
    assert not any("submit_scene_detection" in t for t in stage2_allowed)


async def test_stage2_system_prompt_only_inlines_hit_scenarios(
    monkeypatch, settings, skill_loader, spy_tools
) -> None:
    """Stage 2 的 system prompt 文件只包含 stage 1 命中的场景的 L2 详情，
    其他场景不应出现 —— 这正是方案 2 的核心优化点。
    """
    opts = await _capture_both_options(monkeypatch, settings, skill_loader, spy_tools)
    stage2_sp = opts[1].system_prompt
    assert isinstance(stage2_sp, dict)
    assert stage2_sp.get("type") == "file"
    sp_path = Path(stage2_sp["path"])
    if sp_path.is_file():  # finally 已清就跳过
        content = sp_path.read_text(encoding="utf-8")
        # stage 1 命中了 S03，所以 S03 必须在
        assert "S03" in content
        # 其他没命中的（如 S07 / S11）不应该 inline 完整 L2 内容
        # 不能简单断言 ID 不在（meta list 可能有），但 L2 内容里的特征字符串不该出现
        # 用一个 S03 之外场景的独有内容做反向断言
        # 安全做法：断言长度比"全 12 inline"显著小
        # 全 inline 22-36k 字符；只 inline 1 个场景应该 < 18k
        assert len(content) < 25000, (
            f"stage 2 system prompt 太大 ({len(content)} chars)，"
            "可能没有按 stage 1 命中场景过滤"
        )


async def test_stage1_system_prompt_no_l2_content(
    monkeypatch, settings, skill_loader, spy_tools
) -> None:
    """Stage 1 system prompt 必须只含场景目录 meta，不含任何 L2 详情。

    这是方案 2 的关键节流：stage 1 prompt 必须很小（5-8k），太大就失去优化意义。
    """
    opts = await _capture_both_options(monkeypatch, settings, skill_loader, spy_tools)
    stage1_sp = opts[0].system_prompt
    assert isinstance(stage1_sp, dict)
    assert stage1_sp.get("type") == "file"
    sp_path = Path(stage1_sp["path"])
    if sp_path.is_file():
        content = sp_path.read_text(encoding="utf-8")
        # 必须 < 15k 字符（大约 7-8k tokens）；超了就说明 L2 被误注入
        assert len(content) < 15000, (
            f"stage 1 system prompt 太大 ({len(content)} chars)，"
            "可能误注入了 L2 详情"
        )
        # 场景目录里有的 ID 必须出现
        assert "S03" in content


async def test_thinking_enabled_when_budget_positive(
    monkeypatch, skill_loader, spy_tools
) -> None:
    """thinking_budget > 0 时两个 stage 都应传 thinking={'type':'enabled','budget_tokens':N}。"""
    s = Settings(
        agent_timeout_seconds=5,
        safety_skills_root=SKILLS_ROOT,
        agent_thinking_budget_tokens=5000,
        agent_use_two_stage=True,
    )
    opts = await _capture_both_options(monkeypatch, s, skill_loader, spy_tools)
    for i, o in enumerate(opts):
        assert o.thinking is not None, f"stage{i+1} 应启用 thinking"
        assert o.thinking["type"] == "enabled"
        assert o.thinking["budget_tokens"] == 5000


async def test_thinking_disabled_when_budget_zero(
    monkeypatch, skill_loader, spy_tools
) -> None:
    """budget=0 → 两个 stage 都不传 thinking。"""
    s = Settings(
        agent_timeout_seconds=5,
        safety_skills_root=SKILLS_ROOT,
        agent_thinking_budget_tokens=0,
        agent_use_two_stage=True,
    )
    opts = await _capture_both_options(monkeypatch, s, skill_loader, spy_tools)
    for o in opts:
        assert o.thinking is None


async def test_no_native_structured_output_options(
    monkeypatch, settings, skill_loader, spy_tools
) -> None:
    """v3+ 不应再设 output_format（Sonnet 不会用虚拟工具 StructuredOutput
    会触发 retry 死循环；详见 commit 576bf9a 修复记录）。"""
    opts = await _capture_both_options(monkeypatch, settings, skill_loader, spy_tools)
    for i, o in enumerate(opts):
        assert o.output_format is None, (
            f"stage{i+1} 不应设 output_format —— "
            "Sonnet 4.6 不会用 CLI 虚拟工具 StructuredOutput 会触发 retry 失败"
        )


async def test_system_prompt_passed_as_file_not_inline_string(
    monkeypatch, settings, skill_loader, spy_tools
) -> None:
    """回归保护：两个 stage 的 system_prompt 都必须以 {"type":"file","path":...} 形式
    传给 SDK，不能 inline 成字符串 arg。

    动机：inline 12 个场景的 stage 2 system prompt 达 36k 字符，Windows
    CreateProcessW 上限 32,767 字符。Inline 会让 spawn 失败、SDK 误报 "Claude
    Code not found at: claude"。Stage 1 prompt 较小但统一走 file 路径不增加成本。
    """
    opts = await _capture_both_options(monkeypatch, settings, skill_loader, spy_tools)
    for i, o in enumerate(opts):
        sp = o.system_prompt
        assert isinstance(sp, dict), f"stage{i+1} system_prompt 必须是 dict 走 --system-prompt-file"
        assert sp.get("type") == "file"
        assert Path(sp["path"]).name.endswith(".txt")


# ========== AgentRunStats 累加 / tool_call_timings ==========


async def test_cache_tokens_accumulate_across_stages(
    monkeypatch, settings, skill_loader, spy_tools
) -> None:
    """cache_read_tokens / cache_creation_tokens 必须跨两 stage 累加。

    两个 stage 共享 cached system prompt 公共部分 (role + L1 + shared modules)，
    两次 query 各自从 cache 读 + 写。统计应是两次和。
    """
    def stage1_stream():
        async def gen():
            await spy_tools["scene_tool"].handler({"scenes": ["S03"]})
            yield _make_result_message(
                input_tokens=10, output_tokens=20,
                cache_read_input_tokens=5000, cache_creation_input_tokens=500,
            )
        return gen()

    def stage2_stream():
        async def gen():
            await spy_tools["report_tool"].handler(
                {"report_json": json.dumps(VALID_REPORT, ensure_ascii=False)}
            )
            yield _make_result_message(
                input_tokens=20, output_tokens=500,
                cache_read_input_tokens=10000, cache_creation_input_tokens=800,
            )
        return gen()

    monkeypatch.setattr(
        agent_mod, "query", _fake_query_factory(stage1_stream, stage2_stream)
    )

    _, stats = await agent_mod.analyze_image(
        image_bytes=b"x", settings=settings, skill_loader=skill_loader
    )
    assert stats.input_tokens == 10 + 20
    assert stats.output_tokens == 20 + 500
    assert stats.cache_read_tokens == 5000 + 10000
    assert stats.cache_creation_tokens == 500 + 800


async def test_tool_call_timings_have_stage_prefix(
    monkeypatch, settings, skill_loader, spy_tools
) -> None:
    """tool_call_timings 里每条都带 stage 前缀 (stage1./stage2.) 便于事后归因。

    + dispatched_ms 跨阶段共享 t0：stage 1 entries 时间戳必然小于 stage 2 entries。
    """
    from claude_agent_sdk import AssistantMessage, ToolUseBlock
    import asyncio as _asyncio

    def stage1_stream():
        async def gen():
            yield AssistantMessage(
                content=[ToolUseBlock(id="t1", name="Read", input={"file_path": "/tmp/img.jpg"})],
                model="claude-opus-4-7",
            )
            await _asyncio.sleep(0.02)
            await spy_tools["scene_tool"].handler({"scenes": ["S03"]})
            yield _make_result_message()
        return gen()

    def stage2_stream():
        async def gen():
            await _asyncio.sleep(0.02)
            yield AssistantMessage(
                content=[ToolUseBlock(id="t2", name="Read", input={"file_path": "/tmp/img.jpg"})],
                model="claude-opus-4-7",
            )
            await spy_tools["report_tool"].handler(
                {"report_json": json.dumps(VALID_REPORT, ensure_ascii=False)}
            )
            yield _make_result_message()
        return gen()

    monkeypatch.setattr(
        agent_mod, "query", _fake_query_factory(stage1_stream, stage2_stream)
    )

    _, stats = await agent_mod.analyze_image(
        image_bytes=b"x", settings=settings, skill_loader=skill_loader
    )
    # 至少 2 条 (各阶段 1 个 Read，不计 spy 直接调的 submit)
    assert len(stats.tool_call_timings) == 2
    names = [t["name"] for t in stats.tool_call_timings]
    assert names[0].startswith("stage1.")
    assert names[1].startswith("stage2.")
    # 时间戳跨阶段共享 t0 → stage2 严格大于 stage1
    assert stats.tool_call_timings[1]["dispatched_ms"] > stats.tool_call_timings[0]["dispatched_ms"]


async def test_load_scenario_skill_no_longer_in_allowed_tools(
    monkeypatch, settings, skill_loader, spy_tools
) -> None:
    """回归保护：load_scenario_skill 工具早已下线，两个 stage 都不应包含。"""
    opts = await _capture_both_options(monkeypatch, settings, skill_loader, spy_tools)
    for i, o in enumerate(opts):
        assert not any("load_scenario_skill" in t for t in o.allowed_tools), (
            f"stage{i+1} 不应包含 load_scenario_skill: {o.allowed_tools}"
        )


# ========== 单阶段模式（生产默认）路径覆盖 ==========


async def test_single_stage_only_one_query_call(
    monkeypatch, single_stage_settings, skill_loader, spy_tools
) -> None:
    """生产默认走单阶段：query 只被调用 1 次（直接 stage 2，不经 stage 1）。
    用 stage_id_used 的工具：只应触发 submit_safety_report，没有 submit_scene_detection。
    """
    call_count = {"n": 0}

    async def fake_query(*, prompt, options, transport=None):
        call_count["n"] += 1
        await spy_tools["report_tool"].handler(
            {"report_json": json.dumps(VALID_REPORT, ensure_ascii=False)}
        )
        yield _make_result_message()

    monkeypatch.setattr(agent_mod, "query", fake_query)

    report, stats = await agent_mod.analyze_image(
        image_bytes=b"x", settings=single_stage_settings, skill_loader=skill_loader
    )

    assert call_count["n"] == 1, "单阶段必须只调 query 一次"
    assert report.findings[0].check_id == "B01"
    # 单阶段下 scenarios_loaded 不再由 stage 1 填，保持空（service 层会从
    # report.report_meta.scene_detected 取，那是 v3 的设计）
    assert stats.scenarios_loaded == []


async def test_single_stage_uses_full_inline_system_prompt(
    monkeypatch, single_stage_settings, skill_loader, spy_tools
) -> None:
    """单阶段 system prompt 必须是全 12 场景 inline（不传 scene_ids 给
    PromptBuilder，走 v3 兜底路径）。
    """
    captured_opts: list[Any] = []

    async def fake_query(*, prompt, options, transport=None):
        captured_opts.append(options)
        await spy_tools["report_tool"].handler(
            {"report_json": json.dumps(VALID_REPORT, ensure_ascii=False)}
        )
        yield _make_result_message()

    monkeypatch.setattr(agent_mod, "query", fake_query)
    await agent_mod.analyze_image(
        image_bytes=b"x", settings=single_stage_settings, skill_loader=skill_loader
    )

    assert len(captured_opts) == 1
    sp = captured_opts[0].system_prompt
    assert isinstance(sp, dict) and sp.get("type") == "file"
    sp_path = Path(sp["path"])
    if sp_path.is_file():
        content = sp_path.read_text(encoding="utf-8")
        # 全 inline 应包含所有 12 个场景 ID
        for sid in ("S01", "S05", "S12"):
            assert sid in content, f"单阶段全 inline 应含 {sid}"
        # 长度显著大于 stage 1 prompt（~1.5k）
        assert len(content) > 15000


async def test_single_stage_no_scene_detection_tool_in_allowed_tools(
    monkeypatch, single_stage_settings, skill_loader, spy_tools
) -> None:
    """单阶段不调 stage 1，allowed_tools 不应包含 submit_scene_detection。"""
    captured_opts: list[Any] = []

    async def fake_query(*, prompt, options, transport=None):
        captured_opts.append(options)
        await spy_tools["report_tool"].handler(
            {"report_json": json.dumps(VALID_REPORT, ensure_ascii=False)}
        )
        yield _make_result_message()

    monkeypatch.setattr(agent_mod, "query", fake_query)
    await agent_mod.analyze_image(
        image_bytes=b"x", settings=single_stage_settings, skill_loader=skill_loader
    )

    allowed = captured_opts[0].allowed_tools
    assert "Read" in allowed
    assert any("submit_safety_report" in t for t in allowed)
    assert not any("submit_scene_detection" in t for t in allowed), (
        f"单阶段不应含 submit_scene_detection: {allowed}"
    )
