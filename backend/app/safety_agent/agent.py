"""v2 主分析入口 —— 两阶段 Claude Agent SDK + 自定义 MCP 工具路径。

架构演进（v0 → v4）：
- v0：模型自由打印 JSON → 容易跑偏
- v1：submit_safety_report 自定义工具提交 → 工作但 ~14s wrap-up
- v2（短暂存在）：native structured output (output_format=json_schema) ——
  CLI 注入虚拟工具 `StructuredOutput`。Sonnet 4.6 不会用 → 5 次 retry 全空、
  超时。回退到 v3。
- v3：回到 submit 工具路径，inline 全部 12 个场景到 system prompt（22k）。
  Opus 实测 115s；Sonnet 即使 thinking=0 + 400s timeout 也跑不完。
- v4（当前）：两阶段。Stage 1 用极简 prompt（5-8k）做场景识别，stage 2 只
  inline 命中场景的 L2（8-12k）。目的：通过缩短 stage 2 上下文降低首 token
  延迟 + 模型推理负担。stage 1 失败自动降级到 inline 全部场景（即 v3 行为）。

两阶段流程：
1. 写图片到临时文件、stage 1 system prompt 写到文件
2. Stage 1：用 build_stage1_system_prompt + submit_scene_detection 工具，
   要求模型识别命中场景；从 scene_sink 取结果
3. Stage 2：用 build_system_prompt(scene_ids=...) + submit_safety_report，
   只 inline 命中场景的 L2 清单，跑完整分析；从 report_sink 取结果
4. 合并 stats：tokens / cost / tool_calls 累加；tool_call_timings 加 stage 前缀
   保留时间戳；scenarios_loaded = stage 1 返回的场景列表
"""
from __future__ import annotations

import asyncio
import logging
import tempfile
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKError,
    Message,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    create_sdk_mcp_server,
    query,
)

from app.config import Settings
from app.errors import LLMCallError, LLMTimeoutError
from app.safety_agent.loader import SkillLoader
from app.safety_agent.prompt import PromptBuilder
from app.safety_agent.tools import (
    SAFETY_MCP_SERVER_NAME,
    build_safety_tools,
    build_scene_detection_tool,
)
from app.schemas.report_v2 import ReportV2Payload

logger = logging.getLogger(__name__)

# allowed_tools 必须包含 Read（Agent 用它把临时图片文件读进 context），
# 以及自定义工具的 mcp__前缀全名（SDK 把工具名 namespace 化为 mcp__<server>__<name>）。
_READ_TOOL = "Read"
_SUBMIT_TOOL_FQN = f"mcp__{SAFETY_MCP_SERVER_NAME}__submit_safety_report"
_DETECT_TOOL_FQN = f"mcp__{SAFETY_MCP_SERVER_NAME}__submit_scene_detection"


class AgentRunStats:
    """单次分析的统计信息（跨两阶段累加）。"""

    def __init__(self) -> None:
        self.tool_calls: int = 0
        # v4：stage 1 识别出的命中场景 ID 列表（直接来自模型 submit_scene_detection）
        self.scenarios_loaded: list[str] = []
        self.elapsed_ms: int = 0
        # 以下 token / cost 字段跨两阶段累加（_drain 改成 += 而非 =）
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        # prompt caching 流量 —— 字段名对齐 Anthropic API usage
        self.cache_read_tokens: int = 0
        self.cache_creation_tokens: int = 0
        self.cost_usd: float = 0.0
        # 每次 tool dispatch 记一条 {seq,name,dispatched_ms}。
        # 跨阶段时 dispatched_ms 共享同一个 t0（analyze_image 开始时刻），
        # 所以 stage 1 entries 在前、stage 2 entries 时间戳更大。
        self.tool_call_timings: list[dict[str, Any]] = []


def _short_tool_name(fqn: str) -> str:
    """mcp__safety__submit_safety_report → submit_safety_report；Read → Read。"""
    return fqn.split("__")[-1] if fqn.startswith("mcp__") else fqn


async def _drain(
    stream: AsyncIterator[Message],
    stats: AgentRunStats,
    *,
    t0: float,
    stage_tag: str = "",
) -> None:
    """消费整个消息流；顺路抽统计 + 记 tool 调用 + 打 dispatched_ms 时间戳。

    Args:
        t0: 全局起算点（analyze_image 起跑时间），所有 stage 共享
        stage_tag: "stage1." / "stage2."，加在 tool name 前面便于事后分析
                   两阶段哪一段慢；空串 = 不加前缀（向后兼容旧单测）

    跨阶段调用时 stats 同一对象、tokens/cost 用 `+=` 累加（之前是 `=`）。
    """
    async for msg in stream:
        if isinstance(msg, AssistantMessage):
            # 整条消息共享一个 dispatched_ms —— 模型一帧批发，SDK 无法再细分
            dispatched_ms = int((time.monotonic() - t0) * 1000)
            for block in msg.content:
                if isinstance(block, ToolUseBlock):
                    stats.tool_calls += 1
                    stats.tool_call_timings.append({
                        "seq": stats.tool_calls,
                        "name": f"{stage_tag}{_short_tool_name(block.name)}",
                        "dispatched_ms": dispatched_ms,
                    })
                elif isinstance(block, TextBlock):
                    pass  # Agent 自由文本不打印
        elif isinstance(msg, ResultMessage):
            usage: Any = getattr(msg, "usage", None) or {}
            # `+=` 跨 stage 累加（v3 之前是 `=`，单 stage 没影响；v4 多 stage 必须）
            stats.input_tokens += int(usage.get("input_tokens", 0) or 0)
            stats.output_tokens += int(usage.get("output_tokens", 0) or 0)
            stats.cache_read_tokens += int(usage.get("cache_read_input_tokens", 0) or 0)
            stats.cache_creation_tokens += int(
                usage.get("cache_creation_input_tokens", 0) or 0
            )
            stats.cost_usd += float(getattr(msg, "total_cost_usd", 0.0) or 0.0)


def _build_options(
    settings: Settings,
    system_prompt: str | dict[str, Any],
    mcp_server: Any,
    allowed_tool_fqns: list[str],
) -> ClaudeAgentOptions:
    """组装 ClaudeAgentOptions。抽出来方便单测断言（无副作用纯构造）。"""
    opts_kwargs: dict[str, Any] = dict(
        system_prompt=system_prompt,
        model=settings.agent_model,
        cli_path=settings.claude_cli_path,
        mcp_servers={SAFETY_MCP_SERVER_NAME: mcp_server},
        allowed_tools=[_READ_TOOL] + allowed_tool_fqns,
        max_turns=settings.agent_max_turns,
        permission_mode="bypassPermissions",
    )
    if settings.agent_thinking_budget_tokens > 0:
        opts_kwargs["thinking"] = {
            "type": "enabled",
            "budget_tokens": settings.agent_thinking_budget_tokens,
        }
    return ClaudeAgentOptions(**opts_kwargs)


def _write_temp(content: str | bytes, suffix: str) -> Path:
    """写临时文件，返回绝对路径。调用方负责 finally 删。"""
    mode = "wb" if isinstance(content, bytes) else "w"
    encoding = None if isinstance(content, bytes) else "utf-8"
    with tempfile.NamedTemporaryFile(
        suffix=suffix, delete=False, mode=mode, encoding=encoding
    ) as f:
        f.write(content)
        return Path(f.name).resolve()


async def _stage1_detect_scenes(
    image_path: Path,
    settings: Settings,
    skill_loader: SkillLoader,
    stats: AgentRunStats,
    t0: float,
    deadline: float,
) -> list[str]:
    """Stage 1：场景识别。返回命中场景 ID 列表（可能为空）。

    失败（超时 / SDK 异常 / 模型未调工具 / 全部 ID 非法）→ 返回空列表，
    让调用方走"全 12 个场景"兜底路径。不在这里 raise —— 让 stage 2 仍有机会跑。
    """
    scene_sink: list[list[str]] = []
    tools = build_scene_detection_tool(skill_loader, scene_sink)
    mcp_server = create_sdk_mcp_server(
        name=SAFETY_MCP_SERVER_NAME, version="1.0.0", tools=tools
    )

    builder = PromptBuilder(skill_loader)
    sysprompt_path = _write_temp(builder.build_stage1_system_prompt(), ".txt")
    try:
        user_msg = builder.build_stage1_user_message()
        composed = (
            f"{user_msg}\n\n"
            f"图片路径：{image_path}\n"
            f"请先用 Read 工具读取这张图片，再判断命中场景。"
        )
        options = _build_options(
            settings,
            {"type": "file", "path": str(sysprompt_path)},
            mcp_server,
            [_DETECT_TOOL_FQN],
        )

        timeout = max(deadline - time.monotonic(), 1.0)
        try:
            await asyncio.wait_for(
                _drain(
                    query(prompt=composed, options=options),
                    stats,
                    t0=t0,
                    stage_tag="stage1.",
                ),
                timeout=timeout,
            )
        except (TimeoutError, ClaudeSDKError) as exc:
            logger.warning(
                "v2 stage1 failed (will fallback to all scenarios)",
                extra={"err_type": type(exc).__name__, "err": str(exc)[:200]},
            )
            return []

        if not scene_sink:
            logger.warning(
                "v2 stage1 ended without submit_scene_detection call "
                "(will fallback to all scenarios)",
                extra={"tool_calls_so_far": stats.tool_calls},
            )
            return []
        return scene_sink[-1]
    finally:
        try:
            sysprompt_path.unlink(missing_ok=True)
        except OSError:
            pass


async def _stage2_analyze(
    image_path: Path,
    scene_ids: list[str] | None,
    settings: Settings,
    skill_loader: SkillLoader,
    extra_context: str,
    stats: AgentRunStats,
    t0: float,
    deadline: float,
) -> ReportV2Payload:
    """Stage 2：根据 stage 1 命中场景做深度安全分析。

    scene_ids=None 或 [] → inline 全部 12 个场景（兜底，等价 v3 单阶段）。
    """
    report_sink: list[ReportV2Payload] = []
    tools = build_safety_tools(skill_loader, report_sink)
    mcp_server = create_sdk_mcp_server(
        name=SAFETY_MCP_SERVER_NAME, version="1.0.0", tools=tools
    )

    builder = PromptBuilder(skill_loader)
    # scene_ids 为 None 或空 → 全 inline 兜底
    effective_scene_ids = scene_ids if scene_ids else None
    sysprompt_path = _write_temp(
        builder.build_system_prompt(scene_ids=effective_scene_ids), ".txt"
    )
    try:
        user_msg = builder.build_initial_user_message(
            extra_context=extra_context, scene_ids=effective_scene_ids
        )
        composed = (
            f"{user_msg}\n\n"
            f"图片路径：{image_path}\n"
            f"请先用 Read 工具读取这张图片，再按上述流程分析。"
        )
        options = _build_options(
            settings,
            {"type": "file", "path": str(sysprompt_path)},
            mcp_server,
            [_SUBMIT_TOOL_FQN],
        )

        timeout = max(deadline - time.monotonic(), 1.0)
        try:
            await asyncio.wait_for(
                _drain(
                    query(prompt=composed, options=options),
                    stats,
                    t0=t0,
                    stage_tag="stage2.",
                ),
                timeout=timeout,
            )
        except TimeoutError as exc:
            raise LLMTimeoutError(
                f"v2 Agent stage2 分析超时（总预算 {settings.agent_timeout_seconds}s）"
            ) from exc
        except ClaudeSDKError as exc:
            raise LLMCallError(f"Claude Agent SDK stage2 调用失败: {exc}") from exc

        if not report_sink:
            raise LLMCallError(
                "Agent stage2 结束但未调用 submit_safety_report —— 无最终报告。"
                f" tool_calls={stats.tool_calls}"
            )
        return report_sink[-1]
    finally:
        try:
            sysprompt_path.unlink(missing_ok=True)
        except OSError:
            pass


async def analyze_image(
    image_bytes: bytes,
    settings: Settings,
    skill_loader: SkillLoader,
    extra_context: str = "",
) -> tuple[ReportV2Payload, AgentRunStats]:
    """跑一次 v2 分析。按 settings.agent_use_two_stage 分派到单阶段或两阶段。

    - **单阶段（默认 / 生产）**：直接 _stage2_analyze(scene_ids=None) 走全 12 inline，
      实测 ~115s（Opus）。
    - **两阶段（实验）**：_stage1_detect_scenes → _stage2_analyze(scene_ids=stage1) ；
      实测比单阶段慢 ~76%（202s）；保留代码给未来"Haiku stage 1"等优化思路用。

    Raises:
        LLMTimeoutError: stage 2 超过剩余预算（总预算 settings.agent_timeout_seconds）
        LLMCallError: stage 2 SDK 异常 / 没调 submit_safety_report
    """
    stats = AgentRunStats()
    tmp_image: Path | None = None
    started = time.monotonic()
    deadline = started + settings.agent_timeout_seconds
    try:
        tmp_image = _write_temp(image_bytes, ".jpg")

        scene_ids: list[str] = []
        if settings.agent_use_two_stage:
            # Stage 1：场景识别（失败降级到空 → stage 2 全 inline 兜底）
            scene_ids = await _stage1_detect_scenes(
                tmp_image, settings, skill_loader, stats, started, deadline
            )
            stats.scenarios_loaded = list(scene_ids)

        # Stage 2：深度分析。
        # - 单阶段模式：scene_ids=[] → _stage2_analyze 走全 12 inline 兜底
        # - 两阶段模式：scene_ids=stage1 命中场景；空也兜底
        report = await _stage2_analyze(
            tmp_image,
            scene_ids,
            settings,
            skill_loader,
            extra_context,
            stats,
            started,
            deadline,
        )

        stats.elapsed_ms = int((time.monotonic() - started) * 1000)

        logger.info(
            "v2 analysis done: mode=%s stage1_scenes=%s tool_calls=%d "
            "findings=%d elapsed_ms=%d tokens=%d/%d cache=r%d/w%d cost=%.4f "
            "model=%s thinking=%d",
            "two-stage" if settings.agent_use_two_stage else "single-stage",
            scene_ids if settings.agent_use_two_stage else "<n/a>",
            stats.tool_calls,
            len(report.findings),
            stats.elapsed_ms,
            stats.input_tokens,
            stats.output_tokens,
            stats.cache_read_tokens,
            stats.cache_creation_tokens,
            stats.cost_usd,
            settings.agent_model,
            settings.agent_thinking_budget_tokens,
        )
        return report, stats
    finally:
        if tmp_image is not None:
            try:
                tmp_image.unlink(missing_ok=True)
            except OSError:
                pass
